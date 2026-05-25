"""会议语音识别工具 — 可插拔 ASR 后端 + LLM 摘要"""
import ast
import json
import re
import asyncio
from typing import Any, Dict, Optional
from pathlib import Path

from ..base import BaseTool, ToolResult
from ...meeting.asr import display_model_name, get_asr_pool, sync_transcribe
from ...meeting.config import load_meeting_asr_config, resolve_asr_language
from ...meeting.transcript import normalize_transcript_text

SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".wma"}


def _get_whisper_pool():
    return get_asr_pool()


def shutdown_whisper_pool():
    from ...meeting.asr.pool import shutdown_asr_pool

    shutdown_asr_pool()


_sync_transcribe = sync_transcribe


def _extract_chat_content(response: Any) -> str:
    """Normalize Ollama ModelResponse vs OpenAI-compat dict."""
    if isinstance(response, dict):
        return (response.get("content") or "").strip()
    if hasattr(response, "content"):
        return (getattr(response, "content", None) or "").strip()
    return str(response or "").strip()


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
                "description": "语言：zh（普通话简体）/ en / auto（自动检测）",
            },
        },
        "required": ["file_path"],
    }

    def __init__(self, provider=None, model_size: Optional[str] = None):
        self.provider = provider
        cfg = load_meeting_asr_config()
        self.model_size = model_size or cfg.get("model", "small")

    @property
    def model_label(self) -> str:
        return display_model_name()

    def _validate_file(self, file_path: str) -> Optional[str]:
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
        loop = asyncio.get_event_loop()
        pool = get_asr_pool()
        return await loop.run_in_executor(
            pool,
            sync_transcribe,
            file_path,
            language,
            self.model_size,
        )

    async def _generate_summary(self, transcript: str, language: str = "zh", prompt_override: str = None) -> dict:
        if not self.provider:
            return {
                "summary": "",
                "key_points": [],
                "timeline": [],
                "error": "LLM provider 未配置，无法生成摘要",
            }

        markdown_mode = bool(prompt_override)
        if prompt_override:
            prompt = prompt_override.replace("{duration}", "").replace("{language}", language)
            if "markdown" not in prompt.lower():
                prompt += "\n\n请使用 Markdown 格式输出（含 ## 标题、列表、表格等）。"
            prompt += f"\n\n以下是会议转录文本：\n\n{transcript}"
        else:
            prompt = self._build_summary_prompt(transcript, language)
        try:
            from ...models.base import ChatMessage
            system = (
                "你是一位专业的会议记录助手。输出必须使用 Markdown 格式，不要使用 JSON。"
                "请使用简体中文撰写会议纪要。"
                if markdown_mode
                else "你是一位专业的会议记录助手。请使用简体中文撰写会议纪要。"
            )
            messages = [
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self.provider.chat(messages, temperature=0.7, max_tokens=2000)
            content = self._coerce_llm_text(_extract_chat_content(response))
            if not content:
                return {
                    "summary": "",
                    "key_points": [],
                    "timeline": [],
                    "error": "LLM 返回内容为空，请检查会议摘要模型是否可用",
                }
            parsed = self._parse_summary_response(content, markdown_mode=markdown_mode)
            if not (parsed.get("summary") or "").strip():
                return {
                    "summary": "",
                    "key_points": [],
                    "timeline": [],
                    "error": "无法解析 LLM 摘要结果",
                }
            return parsed
        except Exception as e:
            return {
                "summary": "",
                "key_points": [],
                "timeline": [],
                "error": f"摘要生成失败: {e}",
            }

    def _build_summary_prompt(self, transcript: str, language: str = "zh") -> str:
        if language == "zh" or (language or "").startswith("zh"):
            return f"""请对以下会议转录整理为专业会议纪要，使用 Markdown 格式输出，全文使用简体中文。

## 核心摘要
（2-3 句话概括会议全貌）

## 关键要点
- 要点 1
- 要点 2

## 议题与讨论
### 议题一
- 讨论要点与结论

## 行动项
- [ ] 任务描述 @负责人

要求：忠实原文，不编造；专业术语保留原表述。

会议转录文本：
{transcript}
"""
        return f"""Summarize the following meeting transcript as professional meeting notes in Markdown.

## Executive Summary
## Key Points
## Discussion Topics
## Action Items

Meeting transcript:
{transcript}
"""

    @staticmethod
    def _coerce_llm_text(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, dict):
            for key in ("summary", "content", "text", "markdown", "output"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            return json.dumps(raw, ensure_ascii=False)
        if not isinstance(raw, str):
            return str(raw).strip()
        return raw.strip()

    @staticmethod
    def _unescape_literal_newlines(text: str) -> str:
        if "\n" not in text and "\\n" in text:
            return text.replace("\\n", "\n").replace("\\t", "\t")
        return text

    @classmethod
    def _extract_structured_payload(cls, content: str) -> Optional[dict]:
        text = (content or "").strip()
        if not text.startswith("{"):
            return None
        for parser in (json.loads, ast.literal_eval):
            try:
                data = parser(text)
            except Exception:
                continue
            if isinstance(data, dict):
                return data
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            snippet = text[json_start : json_end + 1]
            for parser in (json.loads, ast.literal_eval):
                try:
                    data = parser(snippet)
                except Exception:
                    continue
                if isinstance(data, dict):
                    return data
        return None

    @classmethod
    def _summary_from_payload(cls, data: dict) -> str:
        for key in ("summary", "content", "text", "markdown", "output"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return cls._unescape_literal_newlines(val.strip())
        return ""

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        text = (content or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    @classmethod
    def _extract_loose_dict_field(cls, text: str, field: str) -> str:
        stripped = (text or "").strip()
        patterns = (
            rf"['\"]{re.escape(field)}['\"]\s*:\s*['\"]([\s\S]*?)['\"]\s*\}}",
            rf"['\"]{re.escape(field)}['\"]\s*:\s*['\"]([\s\S]*?)['\"]\s*,",
        )
        for pattern in patterns:
            match = re.search(pattern, stripped)
            if match:
                value = match.group(1).strip()
                if value:
                    return cls._unescape_literal_newlines(value)
        return ""

    @staticmethod
    def _looks_like_markdown(content: str) -> bool:
        text = (content or "").strip()
        if text.startswith("{"):
            return False
        return bool(re.search(r"^#{1,6}\s", text, re.MULTILINE)) or text.startswith("## ")

    @staticmethod
    def _extract_bullet_key_points(content: str, limit: int = 10) -> list:
        points: list = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- ", "* ", "• ")):
                item = stripped.lstrip("-*• ").strip()
                if item and item not in points:
                    points.append(item)
                if len(points) >= limit:
                    break
        return points

    def _parse_summary_response(self, content: str, markdown_mode: bool = False) -> dict:
        content = self._strip_markdown_fence(self._coerce_llm_text(content))
        payload = self._extract_structured_payload(content)
        if payload:
            summary = self._summary_from_payload(payload)
            if summary:
                key_points = payload.get("key_points")
                if not isinstance(key_points, list) or not key_points:
                    key_points = self._extract_bullet_key_points(summary)
                return {
                    "summary": summary,
                    "key_points": key_points,
                    "timeline": payload.get("timeline", []) if isinstance(payload.get("timeline"), list) else [],
                }
        if content.strip().startswith("{"):
            for key in ("summary", "content", "text", "markdown", "output"):
                extracted = self._extract_loose_dict_field(content, key)
                if extracted:
                    return {
                        "summary": extracted,
                        "key_points": self._extract_bullet_key_points(extracted),
                        "timeline": [],
                    }
        content = self._unescape_literal_newlines(content)
        if markdown_mode or self._looks_like_markdown(content):
            return {
                "summary": content,
                "key_points": self._extract_bullet_key_points(content),
                "timeline": [],
            }
        return {
            "summary": content,
            "key_points": self._extract_bullet_key_points(content),
            "timeline": [],
        }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        action = kwargs.get("action", "summarize")
        language = kwargs.get("language")

        error = self._validate_file(file_path)
        if error:
            return ToolResult(success=False, output="", error=error)

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

        metadata = {
            "language": detected_language,
            "duration": duration,
            "segment_count": len(segments),
            "model": result.get("model", self.model_label),
            "backend": result.get("backend"),
        }

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
            return ToolResult(success=True, output=output_text, metadata=metadata)

        return ToolResult(success=True, output=transcript, metadata=metadata)


# Re-export for tests
__all__ = [
    "MeetingRecognizerTool",
    "SUPPORTED_AUDIO_FORMATS",
    "normalize_transcript_text",
    "sync_transcribe",
    "_sync_transcribe",
    "_get_whisper_pool",
    "shutdown_whisper_pool",
]
