"""网络和服务检测工具"""
import asyncio
import socket
from typing import Any, Dict, Optional

import httpx

from ..base import BaseTool, ToolResult


class NetworkTool(BaseTool):
    name: str = "network"
    description: str = "网络检测：ping 主机、测试端口、HTTP 请求测试、DNS 查询"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["ping", "port_check", "http_test", "dns_lookup"],
                "description": "操作类型",
            },
            "host": {"type": "string", "description": "目标主机"},
            "port": {"type": "integer", "description": "端口号"},
            "url": {"type": "string", "description": "HTTP 测试 URL"},
            "method": {"type": "string", "description": "HTTP 方法，默认 GET"},
            "timeout": {"type": "number", "description": "超时秒数，默认 5"},
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "")
        timeout = kwargs.get("timeout", 5)

        if action == "ping":
            return await self._ping(kwargs.get("host"), timeout)
        if action == "port_check":
            return await self._port_check(kwargs.get("host", "localhost"), kwargs.get("port"), timeout)
        if action == "http_test":
            return await self._http_test(kwargs.get("url"), kwargs.get("method", "GET"), timeout)
        if action == "dns_lookup":
            return await self._dns_lookup(kwargs.get("host"))

        return ToolResult(success=False, output="", error=f"未知操作: {action}")

    async def _ping(self, host: Optional[str], timeout: float) -> ToolResult:
        if not host:
            return ToolResult(success=False, output="", error="ping 需要 host")
        try:
            proc = await asyncio.create_subprocess_shell(
                f"ping -c 3 -W {int(timeout * 1000)} {host}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout * 4)
            output = stdout.decode("utf-8", errors="replace")
            return ToolResult(success=proc.returncode == 0, output=output or "ping 无输出")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"ping 失败: {e}")

    async def _port_check(self, host: str, port: Optional[int], timeout: float) -> ToolResult:
        if not port:
            return ToolResult(success=False, output="", error="port_check 需要 port")
        try:
            fut = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return ToolResult(success=True, output=f"{host}:{port} 开放")
        except asyncio.TimeoutError:
            return ToolResult(success=True, output=f"{host}:{port} 超时（可能关闭或被过滤）")
        except (ConnectionRefusedError, OSError):
            return ToolResult(success=True, output=f"{host}:{port} 连接被拒绝（端口关闭）")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"测试失败: {e}")

    async def _http_test(self, url: Optional[str], method: str, timeout: float) -> ToolResult:
        if not url:
            return ToolResult(success=False, output="", error="http_test 需要 url")
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.request(method.upper(), url)
                return ToolResult(
                    success=True,
                    output=f"{method.upper()} {url}\nStatus: {resp.status_code}\nSize: {len(resp.content)} bytes",
                    metadata={"status_code": resp.status_code, "size": len(resp.content)},
                )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"HTTP 测试失败: {e}")

    async def _dns_lookup(self, host: Optional[str]) -> ToolResult:
        if not host:
            return ToolResult(success=False, output="", error="dns_lookup 需要 host")
        try:
            info = await asyncio.get_event_loop().getaddrinfo(host, None)
            ips = list({r[4][0] for r in info})
            return ToolResult(success=True, output=f"{host} → {', '.join(ips)}", metadata={"ips": ips})
        except socket.gaierror as e:
            return ToolResult(success=False, output="", error=f"DNS 解析失败: {e}")
