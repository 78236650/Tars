# TARS WebSocket Channel Implementation
# Layer 1: WebSocket 通道实现

import json
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect
from .base import Channel, ChannelMessage


def now_iso():
    """获取本地时间 ISO 格式（北京时间 UTC+8）"""
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class WebSocketChannel(Channel):
    """WebSocket 通道"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.agent = None

    def set_agent(self, agent):
        """设置 Agent 引用"""
        self.agent = agent

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
        await self.websocket.send_json(event)

    async def stream(self, session_id: str, chunk: str) -> None:
        """流式推送文本片段"""
        await self.websocket.send_json({
            "type": "text_chunk",
            "session_id": session_id,
            "content": chunk,
            "timestamp": now_iso()
        })

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

            await self.send("default", {
                "type": "generation_start",
                "timestamp": now_iso()
            })

            message = await self.receive(raw_message)
            print(f"[WebSocket] 解析后消息内容: {message.content[:200] if message.content else 'empty'}...")

            file_ids = data.get("file_ids")

            if self.agent:
                await self.agent.handle_message(
                    session_id=message.session_id,
                    user_content=message.content,
                    channel=self,
                    file_ids=file_ids,
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


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: dict[str, WebSocketChannel] = {}
        self.agent = None

    def set_agent(self, agent):
        """设置全局 Agent 引用"""
        self.agent = agent

    async def connect(self, session_id: str, websocket: WebSocket) -> WebSocketChannel:
        """接受连接并返回通道实例"""
        await websocket.accept()
        channel = WebSocketChannel(websocket)
        if self.agent:
            channel.set_agent(self.agent)
        self.active_connections[session_id] = channel
        return channel

    def disconnect(self, session_id: str):
        """断开连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_personal_message(self, session_id: str, event: dict):
        """发送个人消息"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send(session_id, event)
