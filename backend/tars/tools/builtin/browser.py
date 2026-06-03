"""浏览器操作工具 — 基于 browser-use

让 TARS 能打开网页、点击、填表、截图等自动操作。
"""
import os
from typing import Any, Dict

from ..base import BaseTool, ToolResult


class BrowserTool(BaseTool):
    name: str = "browser"
    description: str = (
        "打开浏览器执行网页操作，如打开URL、点击按钮、填写表单、提取内容、截图等。"
        "适用于登录系统、数据录入、页面交互等需要真机浏览器的场景。"
        "注意：此操作会打开真实 Chrome 浏览器窗口，耗时较长，请耐心等待。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "要执行的自然语言浏览器任务，如'打开百度搜索TARS并告诉我结果'",
            },
        },
        "required": ["task"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        task = kwargs.get("task", "").strip()
        if not task:
            return ToolResult(success=False, output="", error="请提供浏览器任务描述")

        try:
            from browser_use import Agent, Browser
            from browser_use.llm import ChatDeepSeek

            browser = Browser(headless=False)

            # 从环境变量读取 DeepSeek 配置
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if not api_key:
                # 兜底：从数据库中读取当前端点的 API Key
                try:
                    from ...database import Database
                    from ...database.endpoint import EndpointStore
                    db = Database()
                    store = EndpointStore(db)
                    eps = store.get_all()
                    for ep in eps:
                        if "deepseek" in ep.name.lower() and ep.api_key:
                            api_key = ep.api_key
                            break
                except Exception:
                    pass

            if not api_key:
                return ToolResult(
                    success=False, output="",
                    error="未找到 DeepSeek API Key，请在模型配置中配置 DeepSeek 端点",
                )

            llm = ChatDeepSeek(
                model="deepseek-v4-flash",
                api_key=api_key,
                base_url="https://api.deepseek.com/v1",
                max_tokens=8192,
            )

            agent = Agent(
                task=task,
                llm=llm,
                browser=browser,
                use_vision=False,
            )

            result = await agent.run(max_steps=30)
            await browser.close()

            output = str(result) if result else "任务已完成"
            return ToolResult(
                success=True,
                output=output[:10000],
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return ToolResult(
                success=False,
                output="",
                error=f"浏览器操作失败: {e}",
            )
