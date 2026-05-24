# TARS WebSocket Channel Implementation
# Layer 1: WebSocket 通道实现

import json
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect
from .base import Channel, ChannelMessage


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

            # 用户决策消息（用于 Planner/Executor 的失败决策）
            if data.get("type") == "user_decision":
                if self.agent and hasattr(self.agent, "task_executor") and self.agent.task_executor:
                    self.agent.task_executor.submit_decision(
                        session_id=data.get("session_id", "default"),
                        step_id=data.get("step_id"),
                        decision=data.get("decision", "abort"),
                    )
                return

            # Chat 显式反馈 👍/👎
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

            await self.send("default", {
                "type": "generation_start",
                "timestamp": now_iso()
            })

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

            await self.send(message.session_id, {
                "type": "generation_end",
                "timestamp": now_iso()
            })
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
