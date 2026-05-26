"""会议语音识别 API 路由"""
import os
import uuid
import json
import asyncio
import base64
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..database import Database
from ..meeting.asr import display_model_name, resolve_backend_name
from ..meeting.config import (
    get_whisper_model_options,
    load_meeting_asr_config,
    normalize_whisper_model,
    resolve_asr_language,
    set_meeting_asr_runtime,
)
from ..tools.builtin.meeting_recognizer import MeetingRecognizerTool, SUPPORTED_AUDIO_FORMATS
from ._auth import get_user_store, require_module, resolve_authenticated_principal

router = APIRouter(prefix="/api/meeting", tags=["会议助手"])
secured_router = APIRouter(dependencies=[Depends(require_module("meeting"))])

_transcription_tasks: set[asyncio.Task] = set()

_db: Optional[Database] = None
_meeting_tool: Optional[MeetingRecognizerTool] = None
_vector_store: Any = None
_embedding_provider: Any = None
_wiki_event_handler = None

# 文件限制
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
STORAGE_PATH = "storage/meetings"


def _default_asr_model() -> str:
    return display_model_name()


def set_meeting_wiki_handler(handler) -> None:
    global _wiki_event_handler
    _wiki_event_handler = handler


def init_meeting_api(
    db: Database,
    tool: Optional[MeetingRecognizerTool] = None,
    vector_store: Any = None,
    embedding_provider: Any = None,
) -> None:
    global _db, _meeting_tool, _vector_store, _embedding_provider
    _db = db
    _meeting_tool = tool
    _vector_store = vector_store
    _embedding_provider = embedding_provider
    _recover_stale_transcriptions()


def _resolve_user_id(
    x_tenant_id: Optional[str] = None,
    x_user_id: Optional[str] = None,
) -> str:
    """与前端 X-Tenant-ID（用户 ID）对齐，用于隔离会议记录。"""
    uid = (x_tenant_id or x_user_id or "default").strip()
    return uid or "default"


def _recover_stale_transcriptions(max_age_minutes: int = 180) -> None:
    """将长时间卡在 pending/processing 的任务标为失败，避免界面一直转圈。"""
    if _db is None:
        return
    try:
        conn = _db._get_conn()
        cursor = conn.cursor()
        cutoff = datetime.now(timezone(timedelta(hours=8))) - timedelta(minutes=max_age_minutes)
        cutoff_iso = cutoff.isoformat()
        cursor.execute(
            """
            SELECT id FROM transcriptions
            WHERE status IN ('pending', 'processing') AND created_at < ?
            """,
            (cutoff_iso,),
        )
        stale = [r[0] for r in cursor.fetchall()]
        if not stale:
            return
        msg = "转写超时或进程中断，请重新上传（开发模式 reload 会中断后台任务）"
        for tid in stale:
            cursor.execute(
                "UPDATE transcriptions SET status = ?, error_message = ? WHERE id = ?",
                ("failed", msg, tid),
            )
        conn.commit()
        print(f"[MeetingAPI] 已将 {len(stale)} 条超时转写标为 failed")
    except Exception as e:
        print(f"[MeetingAPI] 恢复超时转写失败: {e}")


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def _get_storage_dir() -> Path:
    project_dir = Path(__file__).parent.parent.parent
    storage_dir = project_dir / STORAGE_PATH
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def _meeting_audio_path(user_id: str, transcription_id: str, suffix: str = ".webm") -> Path:
    user_dir = _get_storage_dir() / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / f"{transcription_id}{suffix}"


def _audio_media_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {
        ".webm": "audio/webm",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".mp4": "audio/mp4",
    }.get(ext, "application/octet-stream")


def _validate_audio_file(filename: str) -> Optional[str]:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_AUDIO_FORMATS:
        return f"不支持的音频格式 '{ext}'，支持: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
    return None


# ========== 提示词模板 ==========

MEETING_PROMPT_TEMPLATES = {
    "general": {
        "name": "通用商务型",
        "description": "适合大多数会议场景，输出完整会议纪要",
        "prompt": """你是一位资深会议秘书。请将以下会议录音转录整理为专业会议纪要。

输出格式：

## 会议信息
- 主题：（从内容推断）
- 时长：{duration}
- 语言：{language}

## 核心摘要
（3-5句话概括会议全貌，突出结论而非过程）

## 议题与讨论

### 议题 1：[标题]
- 背景：
- 讨论要点：
- 结论：

### 议题 2：[标题]
...

## 决策记录
1. [决策内容] — 提出人：xxx

## 行动项
- [ ] [任务描述] @负责人 截止：[日期]

## 遗留问题
- [未解决的问题或需要后续跟进的事项]

要求：
- 使用 Markdown 格式输出（保留标题、列表、表格等结构）
- 忠实原文，不编造内容
- 专业术语保留原文表述
- 时间、数字、人名务必准确
- 无法确定的信息用[?]标注""",
    },
    "executive": {
        "name": "执行摘要型",
        "description": "适合管理层，聚焦决策和行动项",
        "prompt": """你是一位专业的会议记录分析师。请基于以下会议转录，生成一份执行摘要。

输出要求：
1. 【会议概要】一段话概括会议目的、参与方和核心结论（不超过100字）
2. 【关键决策】列出本次会议做出的所有决策，每条包含：决策内容、决策人、影响范围
3. 【行动项】列出所有待办事项，每条包含：任务描述、负责人、截止时间、优先级(高/中/低)
4. 【风险与阻塞】识别讨论中提到的风险、依赖或阻塞项
5. 【下次会议】下次会议时间、议题预告（如有提及）

格式规范：
- 使用 Markdown 格式
- 行动项用表格呈现
- 未明确提及的信息标注"未提及"
- 保持客观，不添加推测内容""",
    },
    "project": {
        "name": "项目进度型",
        "description": "适合研发/项目团队，跟踪进度和技术决策",
        "prompt": """你是一位项目管理助手。请分析以下会议转录，提取项目相关信息。

输出结构：
1. 【进度更新】各模块/负责人汇报的进度摘要
2. 【问题与讨论】会议中提出的问题、争议点及讨论结论
3. 【技术决策】涉及技术方案的选择和理由
4. 【待办清单】
   | 序号 | 任务 | 负责人 | 截止日期 | 状态 |
   |------|------|--------|----------|------|
5. 【依赖关系】跨团队或外部依赖项
6. 【会议效率评估】会议时长 vs 有效决策数量

注意：
- 区分"已完成"和"进行中"的工作
- 对模糊表述标注[需确认]
- 保留关键数据和指标原文""",
    },
}

DEFAULT_TEMPLATE_ID = "general"

# 用户自定义提示词存储（内存 + DB 持久化）
_custom_prompts: Dict[str, str] = {}
_meeting_model_settings: Dict[str, Any] = {}


# ========== Pydantic 模型 ==========

class TranscribeRequest(BaseModel):
    file_path: str
    language: Optional[str] = None
    action: str = "summarize"


class SummarizeRequest(BaseModel):
    transcription_id: str
    summary_type: str = "structured"
    max_length: int = 500
    template_id: Optional[str] = None


class TranscriptionResponse(BaseModel):
    id: str
    user_id: str
    file_name: Optional[str]
    file_size: Optional[int]
    duration: Optional[float]
    language: Optional[str]
    status: str
    transcript: Optional[str]
    summary: Optional[str]
    key_points: Optional[List[str]]
    model_used: Optional[str]
    created_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]


# ========== 辅助函数 ==========

def _transcription_to_dict(t) -> dict:
    """将 Transcription 对象转为 API 响应字典"""
    key_points = []
    if t.key_points:
        try:
            key_points = json.loads(t.key_points)
        except Exception:
            key_points = []
    return {
        "id": t.id,
        "user_id": t.user_id,
        "file_name": t.file_name,
        "file_size": t.file_size,
        "duration": t.duration,
        "language": t.language,
        "status": t.status,
        "transcript": t.transcript,
        "summary": t.summary,
        "key_points": key_points,
        "model_used": t.model_used,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "error_message": t.error_message,
        "approved_at": t.approved_at,
        "knowledge_doc_id": t.knowledge_doc_id,
        "has_audio": bool(t.file_path and os.path.isfile(t.file_path)),
    }


def _schedule_transcription(transcription_id: str, file_path: str, language: Optional[str] = None) -> None:
    """调度后台转写（asyncio 任务，比 BackgroundTasks 更不易在 reload 时丢失状态更新）。"""
    task = asyncio.create_task(_do_transcription(transcription_id, file_path, language))
    _transcription_tasks.add(task)
    task.add_done_callback(_transcription_tasks.discard)


async def _do_transcription(transcription_id: str, file_path: str, language: Optional[str] = None):
    """后台执行转写任务"""
    if _db is None or _meeting_tool is None:
        return

    try:
        _db.update_transcription(transcription_id, status="processing")
        print(f"[MeetingAPI] 开始转写 {transcription_id}: {file_path}")

        result = await _meeting_tool.execute(
            file_path=file_path,
            action="transcribe",
            language=resolve_asr_language(language),
        )

        if result.success:
            metadata = result.metadata or {}
            segments = metadata.get("segments", [])
            _db.update_transcription(
                transcription_id,
                status="completed",
                transcript=result.output,
                language=metadata.get("language"),
                duration=metadata.get("duration"),
                model_used=metadata.get("model") or _meeting_tool.model_size,
                segments=json.dumps(segments, ensure_ascii=False) if segments else None,
            )
            print(f"[MeetingAPI] 转写完成 {transcription_id}")
        else:
            _db.update_transcription(
                transcription_id,
                status="failed",
                error_message=result.error or "转写失败",
            )
            print(f"[MeetingAPI] 转写失败 {transcription_id}: {result.error}")
    except Exception as e:
        _db.update_transcription(
            transcription_id,
            status="failed",
            error_message=str(e),
        )
        print(f"[MeetingAPI] 转写异常 {transcription_id}: {e}")


async def _do_summarization(transcription_id: str, transcript: str, language: Optional[str] = None):
    """后台执行摘要生成任务"""
    if _db is None or _meeting_tool is None:
        return

    try:
        summary_data = await _meeting_tool._generate_summary(transcript, language or "zh")
        err = (summary_data.get("error") or "").strip()
        summary_text = (summary_data.get("summary") or "").strip()
        if err or not summary_text:
            _db.update_transcription(
                transcription_id,
                error_message=err or "摘要生成结果为空",
            )
            return

        _db.update_transcription(
            transcription_id,
            status="completed",
            summary=summary_text,
            key_points=json.dumps(summary_data.get("key_points", []), ensure_ascii=False),
            summary_type="structured",
        )
        if _wiki_event_handler is not None:
            row = _db.get_transcription(transcription_id)
            title = (row.title if row and getattr(row, "title", None) else None) or f"会议 {transcription_id[:8]}"
            source = f"{transcript}\n\n## 摘要\n{summary_text}"
            task = asyncio.create_task(
                _wiki_event_handler.on_meeting_ended(source, title)
            )
            _transcription_tasks.add(task)
            task.add_done_callback(_transcription_tasks.discard)
    except Exception as e:
        _db.update_transcription(
            transcription_id,
            error_message=f"摘要生成失败: {e}",
        )


# ========== API 路由 ==========

@secured_router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    x_tenant_id: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
):
    """上传音频文件并开始转写"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    # 验证文件名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 验证格式
    format_error = _validate_audio_file(file.filename)
    if format_error:
        raise HTTPException(status_code=400, detail=format_error)

    # 读取文件内容
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    # 验证大小
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（>{MAX_FILE_SIZE // 1024 // 1024}MB），请压缩后重试",
        )

    user_id = _resolve_user_id(x_tenant_id, x_user_id)
    asr_language = resolve_asr_language(language)

    # 保存文件
    storage_dir = _get_storage_dir()
    user_dir = storage_dir / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(datetime.now().timestamp())
    safe_name = Path(file.filename).name
    file_path = user_dir / f"{timestamp}_{safe_name}"

    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    # 创建数据库记录
    transcription = _db.create_transcription(
        user_id=user_id,
        file_path=str(file_path),
        file_name=safe_name,
        file_size=len(content),
        language=asr_language or "auto",
        model_used=_default_asr_model(),
    )

    _schedule_transcription(transcription.id, str(file_path), language)

    return {
        "success": True,
        "transcription": _transcription_to_dict(transcription),
    }


@secured_router.post("/transcribe")
async def transcribe_audio(request: TranscribeRequest):
    """对已有文件执行转写"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    file_path = request.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    format_error = _validate_audio_file(file_path)
    if format_error:
        raise HTTPException(status_code=400, detail=format_error)

    # 创建记录
    transcription = _db.create_transcription(
        user_id="default",
        file_path=file_path,
        file_name=Path(file_path).name,
        language=resolve_asr_language(request.language) or "auto",
        model_used=_default_asr_model(),
    )

    # 立即执行转写（同步等待）
    await _do_transcription(transcription.id, file_path, request.language)

    # 返回结果
    updated = _db.get_transcription(transcription.id)
    return {
        "success": True,
        "transcription": _transcription_to_dict(updated),
    }


class UpdateSummaryRequest(BaseModel):
    summary: str
    key_points: List[str] = []


@secured_router.put("/{transcription_id}/summary")
async def update_summary(transcription_id: str, request: UpdateSummaryRequest):
    """手动编辑保存摘要和要点"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")
    transcription = _db.get_transcription(transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="转录记录不存在")
    _db.update_transcription(
        transcription_id,
        summary=request.summary,
        key_points=json.dumps(request.key_points, ensure_ascii=False),
    )
    updated = _db.get_transcription(transcription_id)
    return {"success": True, "transcription": _transcription_to_dict(updated)}


@secured_router.post("/summarize")
async def summarize_transcription(request: SummarizeRequest):
    """为已有转录生成摘要"""
    if _db is None or _meeting_tool is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    transcription = _db.get_transcription(request.transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="转录记录不存在")

    if not transcription.transcript:
        raise HTTPException(status_code=400, detail="转录文本为空，请先完成转写")

    # 确定使用的提示词
    template_id = request.template_id or DEFAULT_TEMPLATE_ID
    if template_id == "custom" and "default" in _custom_prompts:
        prompt_template = _custom_prompts["default"]
    elif template_id in MEETING_PROMPT_TEMPLATES:
        prompt_template = MEETING_PROMPT_TEMPLATES[template_id]["prompt"]
    else:
        prompt_template = MEETING_PROMPT_TEMPLATES[DEFAULT_TEMPLATE_ID]["prompt"]

    summary_data = await _meeting_tool._generate_summary(
        transcription.transcript,
        transcription.language or "zh",
        prompt_override=prompt_template,
    )

    err = (summary_data.get("error") or "").strip()
    summary_text = (summary_data.get("summary") or "").strip()
    if err:
        raise HTTPException(status_code=503, detail=err)
    if not summary_text:
        raise HTTPException(status_code=500, detail="摘要生成结果为空，请检查会议摘要模型配置")

    _db.update_transcription(
        request.transcription_id,
        summary=summary_text,
        key_points=json.dumps(summary_data.get("key_points", []), ensure_ascii=False),
        summary_type=request.summary_type,
    )

    updated = _db.get_transcription(request.transcription_id)
    return {
        "success": True,
        "transcription": _transcription_to_dict(updated),
    }


@secured_router.get("/{transcription_id}/audio")
async def get_transcription_audio(
    transcription_id: str,
    x_tenant_id: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
):
    """下载/播放会议原音频（需 API Key）。"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    user_id = _resolve_user_id(x_tenant_id, x_user_id)
    transcription = _db.get_transcription(transcription_id)
    if not transcription or transcription.user_id != user_id:
        raise HTTPException(status_code=404, detail="转录记录不存在")

    file_path = (transcription.file_path or "").strip()
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="原音频文件不存在或已删除")

    filename = transcription.file_name or Path(file_path).name
    return FileResponse(
        file_path,
        media_type=_audio_media_type(file_path),
        filename=filename,
    )


@secured_router.get("/status/{transcription_id}")
async def get_status(transcription_id: str):
    """查询转录状态"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    transcription = _db.get_transcription(transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="转录记录不存在")

    return {
        "success": True,
        "transcription": _transcription_to_dict(transcription),
    }


@secured_router.get("/history")
async def list_history(
    limit: int = 50,
    offset: int = 0,
    x_tenant_id: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
):
    """获取转录历史列表"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    user_id = _resolve_user_id(x_tenant_id, x_user_id)
    transcriptions = _db.list_transcriptions(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "transcriptions": [_transcription_to_dict(t) for t in transcriptions],
        "total": len(transcriptions),
        "limit": limit,
        "offset": offset,
    }


# ========== 提示词设置 API ==========

@secured_router.get("/settings/asr")
async def get_asr_settings():
    """获取语音识别（ASR）配置与可选语言。"""
    cfg = load_meeting_asr_config()
    backend = resolve_backend_name(cfg)
    whisper_model = str(cfg.get("model", "small"))
    return {
        "backend": backend,
        "configured_backend": cfg.get("backend", "whisper"),
        "model": _default_asr_model(),
        "whisper_model": whisper_model,
        "whisper_model_options": get_whisper_model_options(),
        "language_default": cfg.get("language_default", "zh"),
        "output_script": cfg.get("output_script", "simplified"),
        "realtime_mode": (cfg.get("realtime") or {}).get("mode", "transcribe_on_stop"),
        "preprocess_enabled": bool((cfg.get("preprocess") or {}).get("enabled", True)),
        "language_options": [
            {"id": "auto", "label": "自动检测"},
            {"id": "zh", "label": "普通话（简体）"},
            {"id": "en", "label": "英语"},
        ],
    }


class AsrSettingsRequest(BaseModel):
    whisper_model: Optional[str] = None


@secured_router.put("/settings/asr")
async def set_asr_settings(request: AsrSettingsRequest):
    """更新语音识别（Whisper 模型大小等）运行时配置。"""
    if not request.whisper_model:
        raise HTTPException(status_code=400, detail="请指定 whisper_model")
    try:
        model = normalize_whisper_model(request.whisper_model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    current = load_meeting_asr_config()
    set_meeting_asr_runtime({"model": model})
    if current.get("model") != model:
        from ..meeting.asr.pool import shutdown_asr_pool

        shutdown_asr_pool()
    return {
        "success": True,
        "message": f"Whisper 模型已切换为 {model}",
        "whisper_model": model,
        "model": display_model_name(),
    }


@secured_router.get("/settings/templates")
async def get_prompt_templates():
    """获取所有可用的摘要提示词模板"""
    templates = []
    for tid, tpl in MEETING_PROMPT_TEMPLATES.items():
        templates.append({
            "id": tid,
            "name": tpl["name"],
            "description": tpl["description"],
            "prompt": tpl["prompt"],
            "is_default": tid == DEFAULT_TEMPLATE_ID,
        })
    custom = _custom_prompts.get("default")
    return {
        "templates": templates,
        "custom_prompt": custom,
        "active_template": "custom" if custom else DEFAULT_TEMPLATE_ID,
    }


class SaveCustomPromptRequest(BaseModel):
    prompt: str


class MeetingModelRequest(BaseModel):
    provider: str  # "ollama" | "openai_compatible"
    model: str
    endpoint_id: Optional[str] = None


@secured_router.put("/settings/prompt")
async def save_custom_prompt(request: SaveCustomPromptRequest):
    """保存用户自定义摘要提示词"""
    _custom_prompts["default"] = request.prompt
    return {"success": True, "message": "自定义提示词已保存"}


@secured_router.delete("/settings/prompt")
async def reset_prompt():
    """恢复默认提示词（删除自定义）"""
    _custom_prompts.pop("default", None)
    return {"success": True, "message": "已恢复默认提示词", "active_template": DEFAULT_TEMPLATE_ID}


@secured_router.get("/settings/model")
async def get_meeting_model():
    """获取会议助手当前使用的模型"""
    if _meeting_tool is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")
    if _meeting_model_settings:
        return {
            "provider": _meeting_model_settings.get("provider", "ollama"),
            "model": _meeting_model_settings.get("model", ""),
            "endpoint_id": _meeting_model_settings.get("endpoint_id"),
            "source": "independent",
        }
    provider = _meeting_tool.provider
    model_name = getattr(provider, "model", None) or getattr(provider, "current_model", "未配置")
    provider_type = "ollama"
    endpoint_id = None
    base_url = str(getattr(provider, "base_url", "") or "")
    if base_url and "localhost:11434" not in base_url:
        provider_type = "openai_compatible"
        try:
            from ..database import EndpointStore
            from tars.main import db as _main_db

            for ep in EndpointStore(_main_db).get_all():
                if ep.base_url.rstrip("/") == base_url.rstrip("/"):
                    endpoint_id = ep.id
                    break
        except Exception:
            pass
    return {
        "provider": provider_type,
        "model": model_name,
        "endpoint_id": endpoint_id,
        "source": "independent",
    }


@secured_router.put("/settings/model")
async def set_meeting_model(request: MeetingModelRequest):
    """为会议助手设置独立模型（不影响主 Agent）"""
    if _meeting_tool is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    try:
        if request.provider == "ollama":
            from ..models.ollama import OllamaProvider
            new_provider = OllamaProvider(model=request.model)
        elif request.provider == "openai_compatible" and request.endpoint_id:
            from ..database import EndpointStore
            from ..models.custom import CustomProvider
            from tars.main import db as _main_db
            endpoint_store = EndpointStore(_main_db)
            endpoint = endpoint_store.get_by_id(request.endpoint_id)
            if not endpoint:
                raise HTTPException(status_code=404, detail="端点不存在")
            new_provider = CustomProvider(
                base_url=endpoint.base_url,
                model=request.model,
                api_key=endpoint.api_key,
            )
        else:
            raise HTTPException(status_code=400, detail="无效的 provider 配置")

        _meeting_tool.provider = new_provider
        _meeting_model_settings.clear()
        _meeting_model_settings.update(
            {
                "provider": request.provider,
                "model": request.model,
                "endpoint_id": request.endpoint_id,
            }
        )
        return {"success": True, "message": f"会议助手模型已切换为 {request.provider}: {request.model}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型切换失败: {e}")


# ========== 入库知识库 ==========

MEETING_KB_NAME = "会议纪要"
MEETING_KB_LEGACY_NAME = "meeting_notes_kb"


def _ensure_meeting_collection(cursor, tenant_id: str) -> str:
    """在当前租户下获取或创建「会议纪要」知识库。"""
    for name in (MEETING_KB_NAME, MEETING_KB_LEGACY_NAME):
        cursor.execute(
            "SELECT id FROM document_collections WHERE name = ? AND tenant_id = ?",
            (name, tenant_id),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    collection_id = str(uuid.uuid4())
    now = _now()
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (collection_id, tenant_id, MEETING_KB_NAME, "会议助手确认入库的纪要", now, now),
    )
    return collection_id


def _index_failure_detail(result1: dict, result2: dict) -> Optional[str]:
    if result1.get("status") != "indexed":
        return result1.get("error") or str(result1.get("status"))
    if result2.get("status") not in (None, "indexed", "empty"):
        return result2.get("error") or str(result2.get("status"))
    return None


class ApproveToKnowledgeRequest(BaseModel):
    summary: str
    key_points: List[str] = []


@secured_router.post("/{transcription_id}/approve-to-knowledge")
async def approve_to_knowledge(
    transcription_id: str,
    request: ApproveToKnowledgeRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    """确认会议纪要并入库知识库"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    tenant_id = (x_tenant_id or "default").strip() or "default"
    summary = (request.summary or "").strip()
    if not summary:
        raise HTTPException(status_code=400, detail="摘要不能为空，请先生成或填写会议纪要摘要")

    transcription = _db.get_transcription(transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="转录记录不存在")
    if transcription.approved_at:
        raise HTTPException(status_code=400, detail="该记录已入库")

    # 更新摘要和要点
    _db.update_transcription(
        transcription_id,
        summary=summary,
        key_points=json.dumps(request.key_points, ensure_ascii=False),
    )

    if _vector_store is None or _embedding_provider is None:
        raise HTTPException(status_code=500, detail="知识库组件未初始化")

    from ..knowledge.indexer import KnowledgeIndexer

    conn = _db._get_conn()
    cursor = conn.cursor()
    collection_id = _ensure_meeting_collection(cursor, tenant_id)
    conn.commit()

    date_str = transcription.created_at.strftime("%Y-%m-%d") if transcription.created_at else ""
    key_points_text = "\n".join(f"- {p}" for p in request.key_points) if request.key_points else ""
    summary_doc = f"[会议] {transcription.file_name or ''} {date_str}\n\n{summary}\n\n要点:\n{key_points_text}"

    indexer = KnowledgeIndexer(_vector_store, _embedding_provider, db=_db)
    doc_id = str(uuid.uuid4())

    title_base = summary[:20].replace("\n", " ").strip() or (transcription.file_name or "会议纪要")
    doc_title = f"{title_base}({date_str})" if date_str else title_base

    result1 = indexer.index_document(
        text=summary_doc,
        doc_id=f"{doc_id}_summary",
        collection_id=collection_id,
        file_name=doc_title,
        file_type="meeting_summary",
        tenant_id=tenant_id,
    )

    result2: Dict[str, Any] = {"chunk_count": 0, "status": "indexed"}
    if transcription.transcript:
        result2 = indexer.index_document(
            text=transcription.transcript,
            doc_id=f"{doc_id}_transcript",
            collection_id=collection_id,
            file_name=doc_title + "_原文",
            file_type="meeting_transcript",
            tenant_id=tenant_id,
        )

    err = _index_failure_detail(result1, result2)
    if err:
        raise HTTPException(status_code=422, detail=f"知识库索引失败: {err}")

    total_chunks = result1.get("chunk_count", 0) + result2.get("chunk_count", 0)
    if total_chunks <= 0:
        raise HTTPException(status_code=422, detail="知识库索引失败: 未生成任何可检索分块")

    now = _now()
    cursor.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, chunk_count, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (doc_id, collection_id, doc_title, "", "meeting", total_chunks, "indexed", now),
    )
    cursor.execute(
        "UPDATE transcriptions SET approved_at = ?, knowledge_doc_id = ? WHERE id = ?",
        (now, doc_id, transcription_id),
    )
    conn.commit()

    return {
        "success": True,
        "message": "会议纪要已入库知识库",
        "knowledge_doc_id": doc_id,
        "collection_id": collection_id,
        "collection_name": MEETING_KB_NAME,
        "chunk_count": total_chunks,
    }


@secured_router.delete("/{transcription_id}")
async def delete_transcription(transcription_id: str):
    """删除转录记录"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    success = _db.delete_transcription(transcription_id)
    if not success:
        raise HTTPException(status_code=404, detail="转录记录不存在")

    return {"success": True, "message": "转录记录已删除"}


# ========== WebSocket 实时录音转写 ==========

router.include_router(secured_router)


async def _close_ws_unauthorized(websocket: WebSocket, code: int, reason: str) -> None:
    try:
        await websocket.close(code=code, reason=reason[:123])
    except Exception:
        pass


async def _authenticate_meeting_ws(websocket: WebSocket) -> Optional[str]:
    """WebSocket 无法携带自定义 Header（浏览器），使用 query api_key（与 /ws 一致）。"""
    api_key = websocket.query_params.get("api_key", "") or websocket.headers.get(
        "x-api-key", ""
    )
    try:
        principal = resolve_authenticated_principal(
            api_key, None, None, get_user_store()
        )
    except HTTPException as exc:
        await _close_ws_unauthorized(websocket, 4401, str(exc.detail))
        return None

    from ..modules.registry import module_registry

    if not module_registry.is_enabled("meeting"):
        await _close_ws_unauthorized(websocket, 4503, "Module meeting disabled")
        return None

    if not principal.is_admin:
        try:
            from ..gateway.role_template import role_template_manager

            if role_template_manager and not role_template_manager.can_access_module(
                principal.role_template_id, "meeting"
            ):
                await _close_ws_unauthorized(
                    websocket, 4403, "Role cannot access module meeting"
                )
                return None
        except Exception as e:
            await _close_ws_unauthorized(
                websocket, 4503, f"auth subsystem error: {e!r}"
            )
            return None

    return principal.tenant_id


@router.websocket("/ws/record")
async def ws_record(websocket: WebSocket):
    """实时录音：累积音频，定期推送预览转写，停止后精修并入库。"""
    user_id = await _authenticate_meeting_ws(websocket)
    if user_id is None:
        return

    await websocket.accept()

    if _db is None or _meeting_tool is None:
        await websocket.send_json({"type": "error", "message": "会议 API 未初始化"})
        await websocket.close()
        return

    import shutil

    from ..meeting.asr import get_asr_pool, sync_transcribe

    cfg = load_meeting_asr_config()
    rt_cfg = cfg.get("realtime") or {}
    min_chunks_partial = max(1, int(rt_cfg.get("min_audio_chunks_for_partial", 1)))

    lang_hint = websocket.query_params.get("language")
    language = lang_hint if lang_hint else None
    start_time = datetime.now(timezone(timedelta(hours=8)))

    import threading

    transcription_id = str(uuid.uuid4())
    recording_path = str(_meeting_audio_path(user_id, transcription_id, ".webm"))
    Path(recording_path).touch()
    recording_lock = threading.Lock()
    chunk_count = 0
    prev_text = ""
    partial_task: Optional[asyncio.Task] = None
    partial_busy = False

    pending = _db.create_transcription(
        user_id=user_id,
        file_path=recording_path,
        file_name=f"实时录音_{start_time.strftime('%Y%m%d_%H%M%S')}.webm",
        file_size=0,
        language=resolve_asr_language(language) or "auto",
        model_used=_default_asr_model(),
        transcription_id=transcription_id,
    )
    _db.update_transcription(transcription_id, status="processing")
    stop_requested = False

    def _recording_size() -> int:
        try:
            return os.path.getsize(recording_path)
        except OSError:
            return 0

    async def _transcribe_path(path: str) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            get_asr_pool(),
            sync_transcribe,
            path,
            language,
            _meeting_tool.model_size,
        )

    async def _push_partial() -> None:
        nonlocal prev_text, partial_busy
        if chunk_count < min_chunks_partial or _recording_size() < 1024:
            return
        partial_busy = True
        snapshot_fd, snapshot_path = tempfile.mkstemp(suffix=".webm")
        os.close(snapshot_fd)
        try:
            with recording_lock:
                shutil.copy2(recording_path, snapshot_path)
            result = await _transcribe_path(snapshot_path)
            if not result.get("success"):
                print(
                    f"[MeetingWS] 预览转写失败 {transcription_id}: "
                    f"{result.get('error', 'unknown')}"
                )
                return
            full_text = (result.get("text") or "").strip()
            if not full_text or full_text == prev_text:
                return
            delta = (
                full_text[len(prev_text):].strip()
                if prev_text and full_text.startswith(prev_text)
                else full_text
            )
            if not delta:
                delta = full_text
            prev_text = full_text
            _db.update_transcription(
                transcription_id,
                status="processing",
                transcript=full_text,
                file_size=_recording_size(),
            )
            await websocket.send_json({
                "type": "transcript",
                "text": delta,
                "full_text": full_text,
                "partial": True,
                "transcription_id": transcription_id,
            })
        finally:
            partial_busy = False
            try:
                os.unlink(snapshot_path)
            except OSError:
                pass

    async def _finalize(full_text: str, result: dict, *, failed: bool = False, error: str = "") -> None:
        if failed:
            _db.update_transcription(
                transcription_id,
                status="failed",
                error_message=error or "转写失败",
                file_size=_recording_size(),
            )
            return
        model_used = result.get("model") or _default_asr_model()
        detected_lang = result.get("language") or resolve_asr_language(language) or "auto"
        _db.update_transcription(
            transcription_id,
            status="completed",
            transcript=full_text,
            language=detected_lang,
            duration=result.get("duration"),
            model_used=model_used,
            file_size=_recording_size(),
            segments=json.dumps(result.get("segments") or [{"text": full_text}], ensure_ascii=False),
        )

    async def _run_final_transcription() -> dict:
        if chunk_count == 0 or _recording_size() < 1024:
            return {"success": False, "error": "未收到有效录音数据"}
        return await _transcribe_path(recording_path)

    try:
        await websocket.send_json({
            "type": "started",
            "transcription_id": transcription_id,
            "phase": "recording",
        })

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio":
                audio_b64 = data.get("data", "")
                if not audio_b64:
                    continue
                with recording_lock:
                    with open(recording_path, "ab") as rec:
                        rec.write(base64.b64decode(audio_b64))
                chunk_count += 1

                if (
                    chunk_count >= min_chunks_partial
                    and not partial_busy
                    and (partial_task is None or partial_task.done())
                ):
                    partial_task = asyncio.create_task(_push_partial())

            elif msg_type == "stop":
                stop_requested = True
                if partial_task and not partial_task.done():
                    try:
                        await partial_task
                    except Exception:
                        pass
                if chunk_count == 0 or _recording_size() < 1024:
                    await _finalize("", {}, failed=True, error="未收到有效录音数据")
                    await websocket.send_json({"type": "error", "message": "未收到有效录音数据"})
                    break

                await websocket.send_json({"type": "status", "phase": "transcribing"})
                result = await _run_final_transcription()
                if not result.get("success"):
                    err = result.get("error") or "转写失败"
                    if prev_text:
                        await _finalize(prev_text, {"model": _default_asr_model(), "language": language})
                        await websocket.send_json({
                            "type": "done",
                            "transcription_id": transcription_id,
                            "full_text": prev_text,
                            "duration": None,
                            "partial_fallback": True,
                        })
                        break
                    await _finalize("", {}, failed=True, error=err)
                    await websocket.send_json({"type": "error", "message": err, "transcription_id": transcription_id})
                    break

                full_text = (result.get("text") or "").strip() or prev_text
                await _finalize(full_text, result)
                if full_text.strip():
                    asyncio.create_task(
                        _do_summarization(
                            transcription_id,
                            full_text,
                            result.get("language") or resolve_asr_language(language),
                        )
                    )
                await websocket.send_json({
                    "type": "done",
                    "transcription_id": transcription_id,
                    "full_text": full_text,
                    "duration": result.get("duration"),
                    "summarizing": bool(full_text.strip()),
                })
                break

    except WebSocketDisconnect:
        if not stop_requested:
            _db.update_transcription(
                transcription_id,
                status="failed",
                error_message="录音已取消",
            )
            return
        if chunk_count > 0 and _recording_size() >= 1024:
            try:
                result = await _run_final_transcription()
                if result.get("success"):
                    full_text = (result.get("text") or "").strip() or prev_text
                    await _finalize(full_text, result)
                elif prev_text:
                    await _finalize(prev_text, {"model": _default_asr_model(), "language": language})
                else:
                    await _finalize("", {}, failed=True, error=result.get("error") or "转写失败")
            except Exception as e:
                if prev_text:
                    await _finalize(prev_text, {"model": _default_asr_model(), "language": language})
                else:
                    await _finalize("", {}, failed=True, error=str(e))
    except Exception as e:
        await _finalize("", {}, failed=True, error=str(e))
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "transcription_id": transcription_id,
            })
        except Exception:
            pass
    finally:
        if chunk_count > 0 and os.path.isfile(recording_path):
            _db.update_transcription(
                transcription_id,
                file_path=recording_path,
                file_size=_recording_size(),
            )
