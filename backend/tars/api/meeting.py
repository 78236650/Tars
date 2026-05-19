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
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..database import Database
from ..modules.registry import module_registry
from ..tools.builtin.meeting_recognizer import MeetingRecognizerTool, SUPPORTED_AUDIO_FORMATS

router = APIRouter(prefix="/api/meeting", tags=["会议助手"])

_transcription_tasks: set[asyncio.Task] = set()

_db: Optional[Database] = None
_meeting_tool: Optional[MeetingRecognizerTool] = None
_vector_store: Any = None
_embedding_provider: Any = None

# 文件限制
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
STORAGE_PATH = "storage/meetings"


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


async def require_meeting_module(
    x_user_role: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    if not module_registry.is_enabled("meeting"):
        raise HTTPException(
            status_code=503,
            detail="会议助手模块未启用，请在 backend/config/modules.yaml 中将 meeting.enabled 设为 true 并重启后端",
        )
    if x_user_role == "admin":
        return
    try:
        from ..gateway.role_template import role_template_manager
        from tars.main import user_store

        if role_template_manager is None or user_store is None or not x_api_key:
            return
        user = user_store.get_user_by_api_key(x_api_key)
        if not user:
            return
        template_id = getattr(user, "role_template_id", None) or "standard"
        if not role_template_manager.can_access_module(template_id, "meeting"):
            raise HTTPException(status_code=403, detail="当前角色无权使用会议助手，请联系管理员分配 meeting 模块权限")
    except HTTPException:
        raise
    except Exception:
        return


router.dependencies = [Depends(require_meeting_module)]


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
            language=language,
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

        _db.update_transcription(
            transcription_id,
            status="completed",
            summary=summary_data.get("summary", ""),
            key_points=json.dumps(summary_data.get("key_points", []), ensure_ascii=False),
            summary_type="structured",
        )
    except Exception as e:
        _db.update_transcription(
            transcription_id,
            status="failed",
            error_message=f"摘要生成失败: {e}",
        )


# ========== API 路由 ==========

@router.post("/upload")
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
        language=language,
        model_used="base",
    )

    _schedule_transcription(transcription.id, str(file_path), language)

    return {
        "success": True,
        "transcription": _transcription_to_dict(transcription),
    }


@router.post("/transcribe")
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
        language=request.language,
        model_used="base",
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


@router.put("/{transcription_id}/summary")
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


@router.post("/summarize")
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

    _db.update_transcription(
        request.transcription_id,
        summary=summary_data.get("summary", ""),
        key_points=json.dumps(summary_data.get("key_points", []), ensure_ascii=False),
        summary_type=request.summary_type,
    )

    updated = _db.get_transcription(request.transcription_id)
    return {
        "success": True,
        "transcription": _transcription_to_dict(updated),
    }


@router.get("/status/{transcription_id}")
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


@router.get("/history")
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

@router.get("/settings/templates")
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


@router.put("/settings/prompt")
async def save_custom_prompt(request: SaveCustomPromptRequest):
    """保存用户自定义摘要提示词"""
    _custom_prompts["default"] = request.prompt
    return {"success": True, "message": "自定义提示词已保存"}


@router.delete("/settings/prompt")
async def reset_prompt():
    """恢复默认提示词（删除自定义）"""
    _custom_prompts.pop("default", None)
    return {"success": True, "message": "已恢复默认提示词", "active_template": DEFAULT_TEMPLATE_ID}


@router.get("/settings/model")
async def get_meeting_model():
    """获取会议助手当前使用的模型"""
    if _meeting_tool is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")
    provider = _meeting_tool.provider
    model_name = getattr(provider, "model", None) or getattr(provider, "current_model", "未配置")
    provider_type = "ollama"
    if hasattr(provider, "base_url") and "localhost:11434" not in str(getattr(provider, "base_url", "")):
        provider_type = "openai_compatible"
    return {
        "provider": provider_type,
        "model": model_name,
        "source": "independent",
    }


@router.put("/settings/model")
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
            endpoint = endpoint_store.get(request.endpoint_id)
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


@router.post("/{transcription_id}/approve-to-knowledge")
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


@router.delete("/{transcription_id}")
async def delete_transcription(transcription_id: str):
    """删除转录记录"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    success = _db.delete_transcription(transcription_id)
    if not success:
        raise HTTPException(status_code=404, detail="转录记录不存在")

    return {"success": True, "message": "转录记录已删除"}


# ========== WebSocket 实时录音转写 ==========

@router.websocket("/ws/record")
async def ws_record(websocket: WebSocket):
    """实时录音转写：前端每5秒发送音频chunk，后端累积转写"""
    await websocket.accept()

    if _db is None or _meeting_tool is None:
        await websocket.send_json({"type": "error", "message": "会议 API 未初始化"})
        await websocket.close()
        return

    from ..tools.builtin.meeting_recognizer import _sync_transcribe, _get_whisper_pool

    segments_text: List[str] = []
    total_duration = 0.0
    language = None
    start_time = datetime.now(timezone(timedelta(hours=8)))
    prev_text = ""

    # 累积音频文件（WebM chunks 只有第一个有文件头，必须拼接为完整文件）
    audio_file = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
    audio_path = audio_file.name

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio":
                audio_b64 = data.get("data", "")
                chunk_index = data.get("index", len(segments_text))

                if not audio_b64:
                    continue

                # 追加音频数据到累积文件
                audio_bytes = base64.b64decode(audio_b64)
                audio_file.write(audio_bytes)
                audio_file.flush()

                # 转写整个累积文件
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        _get_whisper_pool(),
                        _sync_transcribe,
                        audio_path,
                        language,
                        _meeting_tool.model_size,
                    )

                    if result.get("success") and result.get("text", "").strip():
                        full_text = result["text"].strip()
                        # 只返回新增部分
                        new_text = full_text[len(prev_text):].strip() if len(full_text) > len(prev_text) else full_text
                        if new_text and new_text != prev_text:
                            segments_text.append(new_text)
                            prev_text = full_text
                            if not language and result.get("language"):
                                language = result["language"]
                            total_duration = result.get("duration", 0)

                            await websocket.send_json({
                                "type": "transcript",
                                "text": new_text,
                                "index": chunk_index,
                            })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"转写失败: {e}",
                    })

            elif msg_type == "stop":
                audio_file.close()
                full_text = "\n".join(segments_text).strip()

                # 保存到数据库
                transcription = _db.create_transcription(
                    user_id="default",
                    file_path=audio_path,
                    file_name=f"实时录音_{start_time.strftime('%Y%m%d_%H%M%S')}",
                    file_size=os.path.getsize(audio_path),
                    language=language or "zh",
                    model_used=_meeting_tool.model_size,
                )
                _db.update_transcription(
                    transcription.id,
                    status="completed",
                    transcript=full_text,
                    duration=total_duration,
                    segments=json.dumps([{"text": t} for t in segments_text], ensure_ascii=False),
                )

                await websocket.send_json({
                    "type": "done",
                    "transcription_id": transcription.id,
                    "full_text": full_text,
                    "duration": total_duration,
                })
                break

    except WebSocketDisconnect:
        audio_file.close()
        if segments_text:
            full_text = "\n".join(segments_text).strip()
            transcription = _db.create_transcription(
                user_id="default",
                file_path=audio_path,
                file_name=f"实时录音_{start_time.strftime('%Y%m%d_%H%M%S')}(中断)",
                file_size=os.path.getsize(audio_path) if os.path.exists(audio_path) else 0,
                language=language or "zh",
                model_used=_meeting_tool.model_size,
            )
            _db.update_transcription(
                transcription.id,
                status="completed",
                transcript=full_text,
                duration=total_duration,
                segments=json.dumps([{"text": t} for t in segments_text], ensure_ascii=False),
            )
    except Exception as e:
        audio_file.close()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass

    except WebSocketDisconnect:
        if segments_text:
            full_text = "\n".join(segments_text).strip()
            transcription = _db.create_transcription(
                user_id="default",
                file_path="",
                file_name=f"实时录音_{start_time.strftime('%Y%m%d_%H%M%S')}(中断)",
                file_size=0,
                language=language or "zh",
                model_used=_meeting_tool.model_size,
            )
            _db.update_transcription(
                transcription.id,
                status="completed",
                transcript=full_text,
                duration=total_duration,
                segments=json.dumps([{"text": t} for t in segments_text], ensure_ascii=False),
            )
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
