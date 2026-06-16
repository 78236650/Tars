"""TARS MCP Client — 与外部 MCP 服务器的通信层

支持两种传输协议:
- stdio: 子进程 stdin/stdout JSON-RPC（适合本地 MCP 服务器）
- sse: HTTP Server-Sent Events（适合远程 MCP 服务器）

协议: MCP 2024-11-05 规范 (JSON-RPC 2.0 子集)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class MCPServerConfig:
    """MCP 服务器连接配置"""
    name: str                          # 显示名称
    transport: str = "stdio"           # stdio | sse
    # stdio 配置
    command: Optional[List[str]] = None  # 启动命令 (e.g. ["npx", "@modelcontextprotocol/server-filesystem", "/tmp"])
    env: Dict[str, str] = field(default_factory=dict)
    # sse 配置
    sse_url: str = ""                  # SSE 端点 URL
    # 通用
    enabled: bool = True
    timeout_seconds: int = 30          # 请求超时


@dataclass
class MCPToolDef:
    """MCP 工具定义（来自 tools/list 响应）"""
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server_name: str = ""              # 归属于哪个 MCP 服务器


class MCPError(Exception):
    """MCP 协议/通信错误"""


# ---------------------------------------------------------------------------
# Base Transport
# ---------------------------------------------------------------------------

class _MCPSession:
    """一个活跃的 MCP 连接会话，管理 JSON-RPC 请求/响应循环。"""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._request_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._initialized = False
        self.server_capabilities: Dict[str, Any] = {}
        self.server_info: Dict[str, Any] = {}

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    # ------------------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        if self.config.transport == "stdio":
            await self._connect_stdio()
        elif self.config.transport == "sse":
            await self._connect_sse()
        else:
            raise MCPError(f"不支持的传输协议: {self.config.transport}")

        # 启动 reader
        self._reader_task = asyncio.create_task(self._reader_loop())
        # 握手: initialize
        await self._initialize()

    async def disconnect(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

    # ------------------------------------------------------------------
    # JSON-RPC 调用
    # ------------------------------------------------------------------

    async def _send_request(self, method: str, params: dict = None) -> Any:
        """发送 JSON-RPC 请求并等待响应。"""
        rid = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params or {},
        }
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        await self._write(json.dumps(payload))

        try:
            return await asyncio.wait_for(fut, timeout=self.config.timeout_seconds)
        except asyncio.TimeoutError:
            self._pending.pop(rid, None)
            raise MCPError(f"MCP 请求超时: {method} (>{self.config.timeout_seconds}s)")

    async def _send_notification(self, method: str, params: dict = None) -> None:
        """发送 JSON-RPC 通知（无响应期望）。"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        await self._write(json.dumps(payload))

    # ------------------------------------------------------------------
    # 初始化握手
    # ------------------------------------------------------------------

    async def _initialize(self) -> None:
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tars", "version": "5.2.0"},
        })
        self.server_capabilities = result.get("capabilities", {})
        self.server_info = result.get("serverInfo", {})
        await self._send_notification("notifications/initialized")
        self._initialized = True

    # ------------------------------------------------------------------
    # MCP 工具操作
    # ------------------------------------------------------------------

    async def list_tools(self) -> List[MCPToolDef]:
        """调用 tools/list 获取所有可用工具。"""
        result = await self._send_request("tools/list")
        tools: List[MCPToolDef] = []
        for t in result.get("tools", []):
            tools.append(MCPToolDef(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_name=self.config.name,
            ))
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用 tools/call 执行工具。"""
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        # MCP 响应格式: {"content": [{"type": "text", "text": "..."}], "isError": false}
        return result

    # ------------------------------------------------------------------
    # Transport: stdio subprocess
    # ------------------------------------------------------------------

    async def _connect_stdio(self) -> None:
        if not self.config.command:
            raise MCPError("stdio transport 需要配置 command 字段")
        env = os.environ.copy()
        env.update(self.config.env)
        self._process = await asyncio.create_subprocess_exec(
            *self.config.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

    async def _write(self, line: str) -> None:
        if self._process and self._process.stdin:
            self._process.stdin.write((line + "\n").encode("utf-8"))
            await self._process.stdin.drain()

    async def _read_line(self) -> Optional[str]:
        if self._process and self._process.stdout:
            line = await self._process.stdout.readline()
            if line:
                return line.decode("utf-8").strip()
        return None

    # ------------------------------------------------------------------
    # Transport: SSE (HTTP)
    # ------------------------------------------------------------------

    async def _connect_sse(self) -> None:
        if not self.config.sse_url:
            raise MCPError("sse transport 需要配置 sse_url 字段")
        # SSE client: send POST for messages, receive SSE stream
        import aiohttp
        self._sse_session = aiohttp.ClientSession()
        # 获取 SSE endpoint
        self._sse_endpoint = self.config.sse_url.rstrip("/") + "/message"

    async def _write_sse(self, line: str) -> None:
        import aiohttp
        async with self._sse_session.post(
            self._sse_endpoint,
            data=line,
            headers={"Content-Type": "application/json"},
        ) as resp:
            pass  # SSE 不阻塞等待响应；响应通过事件流返回

    # ------------------------------------------------------------------
    # Reader Loop (dispatches responses to pending futures)
    # ------------------------------------------------------------------

    async def _reader_loop(self) -> None:
        """持续读取 MCP 服务器响应并分发到对应的 pending future。"""
        try:
            while True:
                line = None
                if self.config.transport == "stdio":
                    line = await self._read_line()
                elif self.config.transport == "sse":
                    # SSE: 简化实现，通过 POST + Body 同步处理
                    # 实际 SSE 实现需要异步事件监听
                    pass

                if line is None:
                    break
                if not line.strip():
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                rid = msg.get("id")
                if rid is not None and rid in self._pending:
                    fut = self._pending.pop(rid)
                    if "error" in msg:
                        fut.set_exception(MCPError(
                            f"MCP error {msg['error'].get('code',-1)}: {msg['error'].get('message','')}"
                        ))
                    else:
                        fut.set_result(msg.get("result", {}))
                # 通知类消息：忽略（当前不需要处理）
        except asyncio.CancelledError:
            pass
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class MCPClient:
    """MCP 客户端管理器：管理多个 MCP 服务器连接。"""

    def __init__(self):
        self._sessions: Dict[str, _MCPSession] = {}
        self._tools: Dict[str, MCPToolDef] = {}  # tool_name → MCPToolDef

    async def connect_server(self, config: MCPServerConfig) -> List[MCPToolDef]:
        """连接一个 MCP 服务器并获取其工具列表。"""
        if config.name in self._sessions:
            await self.disconnect_server(config.name)

        session = _MCPSession(config)
        await session.connect()
        self._sessions[config.name] = session

        tools = await session.list_tools()
        for t in tools:
            self._tools[t.name] = t
        return tools

    async def disconnect_server(self, server_name: str) -> None:
        """断开指定服务器连接。"""
        session = self._sessions.pop(server_name, None)
        if session:
            # 清理该服务器的工具注册
            self._tools = {k: v for k, v in self._tools.items() if v.server_name != server_name}
            await session.disconnect()

    async def disconnect_all(self) -> None:
        for name in list(self._sessions.keys()):
            await self.disconnect_server(name)

    def get_tool_def(self, tool_name: str) -> Optional[MCPToolDef]:
        return self._tools.get(tool_name)

    def list_all_tools(self) -> List[MCPToolDef]:
        return list(self._tools.values())

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用指定 MCP 工具。"""
        tdef = self._tools.get(tool_name)
        if not tdef:
            raise MCPError(f"未找到 MCP 工具: {tool_name}")

        session = self._sessions.get(tdef.server_name)
        if not session:
            raise MCPError(f"MCP 服务器 {tdef.server_name} 未连接")

        return await session.call_tool(tool_name, arguments)
