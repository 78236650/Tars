"""会议语音识别工具 — 基于 faster-whisper 的音频转录与 LLM 摘要生成"""
import os
import json
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, Optional
from pathlib import Path

from ..base import BaseTool, ToolResult


# 全局进程池（Whisper 是 CPU 密集型，限制 1 worker 避免内存爆炸）
_whisper_pool: Optional[ProcessPoolExecutor] = None

# 支持的音频格式
SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".wma"}


def _get_whisper_pool() -> ProcessPoolExecutor:
    global _whisper_pool
    if _whisper_pool is None:
        _whisper_pool = ProcessPoolExecutor(max_workers=1)
    return _whisper_pool


def shutdown_whisper_pool():
    global _whisper_pool
    if _whisper_pool is not None:
        _whisper_pool.shutdown(wait=False)
        _whisper_pool = None


def _sync_transcribe(file_path: str, language: Optional[str] = None, model_size: str = "base") -> dict:
    """在独立进程中执行 Whisper 转写（CPU 密集型，避免阻塞事件循环）"""
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(file_path, language=language, beam_size=5)

        segment_list = []
        texts = []
        for seg in segments:
            texts.append(seg.text)
            segment_list.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
            })

        full_text = "\n".join(texts).strip()
        return {
            "success": True,
            "text": full_text,
            "language": info.language,
            "duration": info.duration,
            "segments": segment_list,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


class MeetingRecognizerTool(BaseTool):
    name: str = "meeting_recognizer"
    description: str = (
        "转录会议录音并生成结构化摘要。"
        "输入音频文件路径，返回转写文本和结构化摘要。"
        "支持 mp3/wav/m4a/mp4/webm 等格式。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "音频文件的绝对路径",
            },
            "action": {
                "type": "string",
                "description": "操作类型：transcribe（仅转写）或 summarize（转写+摘要）",
                "enum": ["transcribe", "summarize"],
                "default": "summarize",
            },
            "language": {
                "type": "string",
                "description": "语言代码，如 zh/en/ja，默认自动检测",
            },
        },
        "required": ["file_path"],
    }

    def __init__(self, provider=None, model_size: str = "base"):
        self.provider = provider
        self.model_size = model_size

    def _validate_file(self, file_path: str) -> Optional[str]:
        """验证文件，返回错误信息或 None"""
        path = Path(file_path)
        if not path.exists():
            return f"文件不存在: {file_path}"
        if not path.is_file():
            return f"路径不是文件: {file_path}"
        ext = path.suffix.lower()
        if ext not in SUPPORTED_AUDIO_FORMATS:
            return f"不支持的音频格式 '{ext}'，支持: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
        return None

    async def _transcribe(self, file_path: str, language: Optional[str] = None) -> dict:
        """异步执行转写（通过进程池）"""
        loop = asyncio.get_event_loop()
        pool = _get_whisper_pool()
        return await loop.run_in_executor(
            pool, _sync_transcribe, file_path, language, self.model_size
        )

    async def _generate_summary(self, transcript: str, language: str = "zh", prompt_override: str = None) -> dict:
        """调用 LLM 生成结构化会议摘要"""
        if not self.provider:
            return {
                "summary": "",
                "key_points": [],
                "timeline": [],
                "error": "LLM provider 未配置，无法生成摘要",
            }

        if prompt_override:
            prompt = prompt_override.replace("{duration}", "").replace("{language}", language)
            prompt += f"\n\n以下是会议转录文本：\n\n{transcript}"
        else:
            prompt = self._build_summary_prompt(transcript, language)
        try:
            from ...models.base import ChatMessage
            messages = [
                ChatMessage(role="system", content="你是一位专业的会议记录助手。"),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self.provider.chat(messages, temperature=0.7, max_tokens=2000)
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_summary_response(content)
        except Exception as e:
            return {
                "summary": "",
                "key_points": [],
                "timeline": [],
                "error": f"摘要生成失败: {e}",
            }

    def _build_summary_prompt(self, transcript: str, language: str = "zh") -> str:
        """构建摘要生成提示词"""
        if language == "zh" or language.startswith("zh"):
            return f"""请对以下会议转录文本生成结构化摘要。

要求：
1. 用 2-3 句话概括会议整体内容
2. 列出 3-7 个关键要点（要点应简洁明了）
3. 按时间线列出主要讨论议题（格式：开始时间 - 议题）

输出格式（严格遵循 JSON）：
{{
  "summary": "会议整体概括...",
  "key_points": ["要点1", "要点2", ...],
  "timeline": [{{"time": "00:00", "content": "开场介绍"}}, ...]
}}

会议转录文本：
{transcript}
"""
        else:
            return f"""Please generate a structured summary of the following meeting transcript.

Requirements:
1. Summarize the overall meeting in 2-3 sentences
2. List 3-7 key points
3. List main discussion topics in timeline format

Output format (strict JSON):
{{
  "summary": "Overall summary...",
  "key_points": ["point 1", "point 2", ...],
  "timeline": [{{"time": "00:00", "content": "Introduction"}}, ...]
}}

Meeting transcript:
{transcript}
"""

    def _parse_summary_response(self, content: str) -> dict:
        """解析 LLM 返回的摘要 JSON"""
        try:
            # 尝试提取 JSON 块
            json_start = content.find("{")
            json_end = content.rfind("}")
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end + 1]
                data = json.loads(json_str)
                return {
                    "summary": data.get("summary", ""),
                    "key_points": data.get("key_points", []),
                    "timeline": data.get("timeline", []),
                }
        except Exception:
            pass

        # fallback：返回原始内容作为 summary
        return {
            "summary": content,
            "key_points": [],
            "timeline": [],
        }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        action = kwargs.get("action", "summarize")
        language = kwargs.get("language")

        # 验证文件
        error = self._validate_file(file_path)
        if error:
            return ToolResult(success=False, output="", error=error)

        # 执行转写
        result = await self._transcribe(file_path, language)
        if not result.get("success"):
            return ToolResult(
                success=False,
                output="",
                error=f"转写失败: {result.get('error', '未知错误')}",
            )

        transcript = result["text"]
        detected_language = result.get("language", language or "auto")
        duration = result.get("duration")
        segments = result.get("segments", [])

        # 构建元数据
        metadata = {
            "language": detected_language,
            "duration": duration,
            "segment_count": len(segments),
        }

        # 如果需要摘要
        if action == "summarize":
            summary_data = await self._generate_summary(transcript, detected_language)
            metadata["summary"] = summary_data.get("summary", "")
            metadata["key_points"] = summary_data.get("key_points", [])
            metadata["timeline"] = summary_data.get("timeline", [])
            if summary_data.get("error"):
                metadata["summary_error"] = summary_data["error"]

            output_text = f"""## 会议摘要

{metadata.get('summary', '')}

## 关键要点
"""
            for i, point in enumerate(metadata.get("key_points", []), 1):
                output_text += f"{i}. {point}\n"

            output_text += f"""
## 转写文本

{transcript}
"""
            return ToolResult(
                success=True,
                output=output_text,
                metadata=metadata,
            )

        # 仅转写
        return ToolResult(
            success=True,
            output=transcript,
            metadata=metadata,
        )
