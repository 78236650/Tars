# TARS WebSocket Channel Implementation
# Layer 1: WebSocket 通道实现

import json
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect
from .base import Channel, ChannelMessage
from ..agent.follow_up_queue import FollowUpItem


def now_iso():
    """获取本地时间 ISO 格式（北京时间 UTC+8）"""
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class WebSocketChannel(Channel):
    """WebSocket 通道"""

    def __init__(self, websocket: WebSocket, tenant_context=None, manager=None, connection_id: str | None = None, request_context: dict | None = None):
        self.websocket = websocket
        self.agent = None
        self.tenant_context = tenant_context
        self.manager = manager
        self.connection_id = connection_id
        self._request_context = request_context or {"transport": "websocket"}
        self._router = None
        self._use_router = False

    def set_agent(self, agent):
        """设置 Agent 引用"""
        self.agent = agent

    def set_outbound_router(self, router, use_router: bool = False) -> None:
        self._router = router
        self._use_router = use_router

    async def receive(self, raw_message: str) -> ChannelMessage:
        """解析 WebSocket 消息"""
        data = json.loads(raw_message)
        return ChannelMessage(
            channel="web",
            user_id=data.get("user_id", "default"),
            session_id=data.get("session_id", "default"),
            content=data.get("content", ""),
            timestamp=datetime.now(timezone(timedelta(hours=8)))
        )

    async def send(self, session_id: str, event: dict) -> None:
        """发送完整事件"""
        if self._use_router and self._router is not None:
            await self._router.send("websocket", session_id, event)
            return
        await self._send_direct(event)

    async def _send_direct(self, event: dict) -> None:
        try:
            await self.websocket.send_json(event)
        except Exception as e:
            print(f"[WebSocket] send_json 失败（客户端可能已断开）: {type(e).__name__}: {e}")
            raise

    async def stream(self, session_id: str, chunk: str) -> None:
        """流式推送文本片段"""
        await self.send(
            session_id,
            {
                "type": "text_chunk",
                "session_id": session_id,
                "content": chunk,
                "timestamp": now_iso(),
            },
        )

    async def handle_message(self, raw_message: str, websocket: WebSocket = None):
        """处理用户消息 - 路由到 Agent 层"""
        print(f"[WebSocket] 收到原始消息: {raw_message[:200]}...")
        try:
            data = json.loads(raw_message)

            if self._is_control_message(data):
                await self._handle_control_message(data)
                return

            session_id = data.get("session_id", "default")
            queue = getattr(self.agent, "follow_up_queue", None) if self.agent else None
            if queue and not queue.try_acquire(session_id):
                pending = queue.enqueue(FollowUpItem.from_raw(raw_message, data))
                await self._emit_queue_status(session_id, pending)
                return

            try:
                await self._execute_agent_turn(raw_message, data)
            finally:
                if queue:
                    await self._drain_follow_up_queue(session_id)
                    queue.mark_idle(session_id)
        except Exception as e:
            print(f"[WebSocket] 消息处理异常: {type(e).__name__}: {e}")
            traceback.print_exc()
            try:
                await self.send("default", {
                    "type": "generation_end",
                    "timestamp": now_iso()
                })
                await self.send("default", {
                    "type": "error",
                    "session_id": "default",
                    "message": f"消息处理失败: {str(e)}",
                    "code": "message_error",
                    "timestamp": now_iso()
                })
            except Exception as send_err:
                print(f"[WebSocket] 发送 error 事件失败（连接可能已关闭）: {send_err}")

    def _is_control_message(self, data: dict) -> bool:
        return data.get("type") in (
            "user_decision",
            "message_feedback",
            "subagent_handoff_action",
            "stop_generation",
        )

    async def _handle_control_message(self, data: dict) -> None:
        if data.get("type") == "user_decision":
            if self.agent and hasattr(self.agent, "task_executor") and self.agent.task_executor:
                self.agent.task_executor.submit_decision(
                    session_id=data.get("session_id", "default"),
                    step_id=data.get("step_id"),
                    decision=data.get("decision", "abort"),
                )
            return

        if data.get("type") == "message_feedback":
            mgr = getattr(self.agent, "evolution_manager", None) if self.agent else None
            collector = mgr.feedback_collector if mgr else None
            if collector:
                tenant_id = getattr(self.tenant_context, "tenant_id", None) or "default"
                user_id = data.get("user_id") or self._request_context.get("user_id", "default")
                feedback = data.get("feedback") or ("up" if data.get("score", 0) > 0 else "down")
                collector.record_explicit_feedback(
                    tenant_id,
                    user_id,
                    data.get("session_id", "default"),
                    str(feedback),
                )
            return

        if data.get("type") == "subagent_handoff_action" and self.agent:
            action = data.get("action", "")
            handoff_id = data.get("handoff_id", "")
            session_id = data.get("session_id", "default")
            tenant_id = getattr(self.tenant_context, "tenant_id", None) or "default"
            ok = await self.agent.handle_subagent_handoff_action(
                handoff_id,
                action,
                channel=self,
                tenant_id=tenant_id,
            )
            if not ok:
                await self.send(session_id, {
                    "type": "error",
                    "session_id": session_id,
                    "message": "子代理审查操作失败或 handoff 不存在",
                    "code": "handoff_error",
                    "timestamp": now_iso(),
                })
            return

        if data.get("type") == "stop_generation":
            await self._handle_stop_generation(data)
            return

    async def _handle_stop_generation(self, data: dict) -> None:
        session_id = data.get("session_id", "default")
        queue = getattr(self.agent, "follow_up_queue", None) if self.agent else None
        if not queue:
            return

        queue.request_cancel(session_id)
        cleared = queue.clear_pending(session_id)

        if cleared:
            await self._emit_queue_status(session_id, 0)

        # 立即响应前端，无论 agent 是否正忙
        # 用户点击停止应立刻看到按钮恢复，不等 agent 检测到取消
        await self.send(session_id, {
            "type": "generation_stopped",
            "session_id": session_id,
            "reason": "user_cancelled",
            "cleared_pending": cleared,
            "timestamp": now_iso(),
        })
        # 如果 agent 正忙（was_busy），generation_end 由 agent 的
        # _abort_if_cancelled 或 finally 块发送；否则立即发
        if not queue.is_busy(session_id):
            await self.send(session_id, {
                "type": "generation_end",
                "session_id": session_id,
                "timestamp": now_iso(),
            })
            queue.reset_cancel(session_id)

    async def _emit_queue_status(self, session_id: str, pending: int) -> None:
        await self.send(session_id, {
            "type": "queue_status",
            "session_id": session_id,
            "pending": pending,
            "timestamp": now_iso(),
        })

    async def _execute_agent_turn(self, raw_message: str, data: dict) -> None:
        session_id = data.get("session_id", "default")
        queue = getattr(self.agent, "follow_up_queue", None) if self.agent else None
        if queue:
            queue.reset_cancel(session_id)

        await self.send(session_id, {
            "type": "generation_start",
            "session_id": session_id,
            "timestamp": now_iso()
        })

        try:
            message = await self.receive(raw_message)
            if self.manager and self.connection_id:
                self.manager.bind_session(message.session_id, self.connection_id)
            print(f"[WebSocket] 解析后消息内容: {message.content[:200] if message.content else 'empty'}...")

            file_ids = data.get("file_ids")

            if self.agent:
                await self.agent.handle_message(
                    session_id=message.session_id,
                    user_content=message.content,
                    channel=self,
                    file_ids=file_ids,
                    tenant_context=self.tenant_context,
                    request_context=self._request_context,
                )
            else:
                print(f"[WebSocket] Agent 未设置!")
                await self.send(message.session_id, {
                    "type": "error",
                    "session_id": message.session_id,
                    "message": "Agent 未初始化",
                    "code": "agent_not_ready",
                    "timestamp": now_iso()
                })
        finally:
            await self.send(session_id, {
                "type": "generation_end",
                "session_id": session_id,
                "timestamp": now_iso()
            })

    async def _drain_follow_up_queue(self, session_id: str) -> None:
        if not self.agent:
            return
        queue = self.agent.follow_up_queue
        if queue.is_cancelled(session_id):
            queue.clear_pending(session_id)
            queue.reset_cancel(session_id)
            await self._emit_queue_status(session_id, 0)
            return
        while True:
            item = queue.pop(session_id)
            if item is None:
                await self._emit_queue_status(session_id, 0)
                return
            await self._emit_queue_status(session_id, queue.pending(session_id))
            data = json.loads(item.raw_message)
            await self._execute_agent_turn(item.raw_message, data)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: dict[str, WebSocketChannel] = {}
        self.session_connections: dict[str, str] = {}
        self.agent = None
        self._router = None
        self._use_router = False

    def set_agent(self, agent):
        """设置全局 Agent 引用"""
        self.agent = agent

    def configure_router(self, router, use_router: bool = False) -> None:
        self._router = router
        self._use_router = use_router

    async def connect(self, connection_id: str, websocket: WebSocket, tenant_context=None, request_context: dict = None) -> WebSocketChannel:
        """接受连接并返回通道实例"""
        await websocket.accept()
        channel = WebSocketChannel(
            websocket,
            tenant_context=tenant_context,
            manager=self,
            connection_id=connection_id,
            request_context=request_context,
        )
        channel.set_outbound_router(self._router, self._use_router)
        if self.agent:
            channel.set_agent(self.agent)
        self.active_connections[connection_id] = channel
        return channel

    def bind_session(self, session_id: str, connection_id: str):
        """将聊天会话绑定到当前连接。"""
        if session_id:
            self.session_connections[session_id] = connection_id

    def unbind_session(self, session_id: str):
        self.session_connections.pop(session_id, None)

    def disconnect(self, connection_id: str):
        """断开连接"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        stale_sessions = [
            session_id
            for session_id, mapped_connection_id in self.session_connections.items()
            if mapped_connection_id == connection_id
        ]
        for session_id in stale_sessions:
            self.unbind_session(session_id)

    async def deliver_to_session(self, session_id: str, event: dict) -> bool:
        """Deliver directly to the bound WebSocket (bypasses ChannelRouter)."""
        connection_id = self.session_connections.get(session_id, session_id)
        if connection_id in self.active_connections:
            await self.active_connections[connection_id]._send_direct(event)
            return True
        return False

    async def send_personal_message(self, session_id: str, event: dict) -> bool:
        """发送个人消息，返回是否成功投递"""
        if self._use_router and self._router is not None:
            connection_id = self.session_connections.get(session_id, session_id)
            if connection_id not in self.active_connections:
                return False
            await self._router.send("websocket", session_id, event)
            return True
        return await self.deliver_to_session(session_id, event)

    async def broadcast(self, event: dict):
        """广播消息到所有活跃连接"""
        stale_ids = []
        for connection_id, channel in list(self.active_connections.items()):
            try:
                await channel._send_direct(event)
            except Exception:
                stale_ids.append(connection_id)
        for connection_id in stale_ids:
            self.disconnect(connection_id)
