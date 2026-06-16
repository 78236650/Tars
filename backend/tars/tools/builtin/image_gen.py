"""TARS Tool - AI 图像生成"""
from typing import Any, Dict

from ..base import BaseTool, ToolResult
from ...generation import AgnesProvider, GenResult

# 全局 Provider 实例（在 main.py 中注入）
_gen_provider: AgnesProvider = None


def init_image_gen(provider: AgnesProvider):
    """注入生成 Provider"""
    global _gen_provider
    _gen_provider = provider


class ImageGenTool(BaseTool):
    """AI 图像生成工具 — 调用 Agnes AI / DALL·E 等生成服务"""

    name: str = "image_gen"
    description: str = (
        "AI 图片生成。根据文字描述创建图片。\n"
        "用于：画图、插图、海报、概念图、Logo 设计、UI mockup 等任何需要生成图片的任务。\n"
        "参数：prompt（必须，中文或英文描述）、negative_prompt（可选，不想出现的内容）、\n"
        "width/height（可选，默认 1024x1024，支持 256/512/768/1024/1440/1792）。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图片描述，越详细越好。支持中文和英文。",
            },
            "negative_prompt": {
                "type": "string",
                "description": "负面提示词——不想在图片中出现的内容。",
            },
            "width": {
                "type": "integer",
                "description": "图片宽度，默认 1024",
                "default": 1024,
            },
            "height": {
                "type": "integer",
                "description": "图片高度，默认 1024",
                "default": 1024,
            },
        },
        "required": ["prompt"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        if _gen_provider is None:
            return ToolResult(
                success=False,
                output="",
                error="图像生成服务未配置。请联系管理员设置 AGNES_API_KEY。",
            )

        prompt = kwargs.get("prompt", "")
        if not prompt:
            return ToolResult(success=False, output="", error="请提供图片描述 (prompt)")

        negative = kwargs.get("negative_prompt", "")
        width = int(kwargs.get("width", 1024))
        height = int(kwargs.get("height", 1024))

        result: GenResult = await _gen_provider.generate_image(
            prompt=prompt,
            negative_prompt=negative,
            width=width,
            height=height,
        )

        if not result.success:
            return ToolResult(
                success=False,
                output=f"图片生成失败: {result.error}",
                error=result.error,
            )

        model = result.metadata.get("model", "unknown")
        size = result.metadata.get("size", "")

        # 构建输出：只返回短文本 + URL（base64 仅放 metadata，不污染 LLM 上下文）
        output_parts = [f"✅ 图片已生成 (模型: {model}, 尺寸: {size})"]
        if result.url:
            output_parts.append(f"图片链接: {result.url}")
        output_parts.append("（图片已渲染在工具卡片中，请直接查看）")

        return ToolResult(
            success=True,
            output="\n".join(output_parts),
            metadata={
                "image_url": result.url,
                "image_base64": result.base64,
                "model": model,
                "size": size,
            },
        )
