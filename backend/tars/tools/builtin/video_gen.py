"""TARS Tool - AI 视频生成"""
from typing import Any, Dict

from ..base import BaseTool, ToolResult
from ...generation import AgnesProvider, GenResult

# 全局 Provider 实例（在 main.py 中注入）
_gen_provider: AgnesProvider = None


def init_video_gen(provider: AgnesProvider):
    """注入生成 Provider"""
    global _gen_provider
    _gen_provider = provider


class VideoGenTool(BaseTool):
    """AI 视频生成工具 — 调用 Agnes AI / Runway 等生成服务"""

    name: str = "video_gen"
    description: str = (
        "AI 视频生成。根据文字描述创建短视频。\n"
        "用于：动画、宣传片片段、概念视频、产品展示等任何需要生成视频的任务。\n"
        "参数：prompt（必须，视频描述）、duration（可选，时长秒数，默认 5）、\n"
        "注意：视频生成是异步的，会先返回任务 ID，随后轮询获取结果。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "视频描述，越详细越好。",
            },
            "duration": {
                "type": "integer",
                "description": "视频时长（秒），默认 5",
                "default": 5,
            },
        },
        "required": ["prompt"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        if _gen_provider is None:
            return ToolResult(
                success=False,
                output="",
                error="视频生成服务未配置。请联系管理员设置 AGNES_API_KEY。",
            )

        prompt = kwargs.get("prompt", "")
        if not prompt:
            return ToolResult(success=False, output="", error="请提供视频描述 (prompt)")

        duration = int(kwargs.get("duration", 5))

        # 提交生成任务，立即返回（视频生成需数分钟，不阻塞 Agent）
        result: GenResult = await _gen_provider.generate_video(
            prompt=prompt, duration=duration,
        )

        if not result.success:
            return ToolResult(
                success=False,
                output=f"视频生成提交失败: {result.error}",
                error=result.error,
            )

        # 快速轮询几秒看是否已完成（某些 provider 可能很快）
        import asyncio
        for _ in range(3):
            await asyncio.sleep(5)
            polled = await _gen_provider.poll_video(result.task_id)
            if polled.success:
                return ToolResult(
                    success=True,
                    output=f"✅ 视频已生成\n视频链接: {polled.url}",
                    metadata={
                        "video_url": polled.url,
                        "thumbnail_url": polled.metadata.get("thumbnail", ""),
                        "task_id": result.task_id,
                        "model": polled.metadata.get("model", "unknown"),
                    },
                )
            if polled.status == "failed":
                return ToolResult(
                    success=False,
                    output=f"视频生成失败: {polled.error}",
                    error=polled.error,
                )

        # 仍在处理中 → 返回进度状态，Agent 继续运行
        return ToolResult(
            success=True,
            output=(
                f"🎬 视频已提交生成\n"
                f"任务 ID: {result.task_id}\n"
                f"描述: {prompt}\n"
                f"预计需要 3-10 分钟，请稍后刷新查看结果。"
            ),
            metadata={
                "task_id": result.task_id,
                "status": "processing",
                "prompt": prompt,
            },
        )
