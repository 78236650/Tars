"""Web Fetch 工具 — 获取网页正文（trafilatura 提取）"""
from typing import Any, Dict

import httpx

from ..base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = (
        "获取网页正文内容（自动提取主要文本，去除导航/广告/脚本）。"
        "用于在 web_search 找到目标 URL 后获取详细内容。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要获取的网页 URL"},
            "max_length": {"type": "integer", "description": "最大返回字符数，默认 5000"},
        },
        "required": ["url"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "").strip()
        max_length = kwargs.get("max_length", 5000)

        if not url:
            return ToolResult(success=False, output="", error="请提供 URL")

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 TARS-Agent/1.0"})
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return ToolResult(success=False, output="", error=f"HTTP 错误: {e.response.status_code}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"获取网页失败: {e}")

        html = resp.text
        extracted = False
        title = ""
        text = ""

        try:
            import trafilatura
            result = trafilatura.extract(html, include_comments=False, include_tables=True)
            if result and len(result) >= 100:
                text = result
                extracted = True
                metadata_obj = trafilatura.extract(html, include_comments=False, output_format="xmltei")
                try:
                    import re
                    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(1).strip()
                except Exception:
                    pass
        except ImportError:
            pass
        except Exception:
            pass

        if not extracted:
            text = f"⚠️ 未能提取正文，返回原始内容:\n\n{html[:max_length]}"
            return ToolResult(
                success=True,
                output=text[:max_length],
                metadata={"url": url, "status_code": resp.status_code, "extracted": False},
            )

        if title:
            output = f"{title}\n\n{text}"
        else:
            output = text

        if len(output) > max_length:
            output = output[:max_length] + "\n... (已截断)"

        return ToolResult(
            success=True,
            output=output,
            metadata={"url": url, "status_code": resp.status_code, "length": len(text), "extracted": True},
        )
