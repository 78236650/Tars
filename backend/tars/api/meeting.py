"""会议语音识别 API 路由"""
import os
import uuid
import json
import asyncio
import base64
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Header, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..database import Database
from ..tools.builtin.meeting_recognizer import MeetingRecognizerTool, SUPPORTED_AUDIO_FORMATS

router = APIRouter(prefix="/api/meeting", tags=["会议助手"])

_db: Optional[Database] = None
_meeting_tool: Optional[MeetingRecognizerTool] = None

# 文件限制
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
STORAGE_PATH = "storage/meetings"


def init_meeting_api(db: Database, tool: Optional[MeetingRecognizerTool] = None) -> None:
    global _db, _meeting_tool
    _db = db
    _meeting_tool = tool


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


# ========== Pydantic 模型 ==========

class TranscribeRequest(BaseModel):
    file_path: str
    language: Optional[str] = None
    action: str = "summarize"


class SummarizeRequest(BaseModel):
    transcription_id: str
    summary_type: str = "structured"
    max_length: int = 500


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
    }


async def _do_transcription(transcription_id: str, file_path: str, language: Optional[str] = None):
    """后台执行转写任务"""
    if _db is None or _meeting_tool is None:
        return

    try:
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
        else:
            _db.update_transcription(
                transcription_id,
                status="failed",
                error_message=result.error or "转写失败",
            )
    except Exception as e:
        _db.update_transcription(
            transcription_id,
            status="failed",
            error_message=str(e),
        )


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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: Optional[str] = None,
    x_user_id: Optional[str] = Header(default="default"),
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

    # 保存文件
    storage_dir = _get_storage_dir()
    user_dir = storage_dir / (x_user_id or "default")
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
        user_id=x_user_id or "default",
        file_path=str(file_path),
        file_name=safe_name,
        file_size=len(content),
        language=language,
        model_used="base",
    )

    # 后台异步转写
    background_tasks.add_task(
        _do_transcription,
        transcription.id,
        str(file_path),
        language,
    )

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

    summary_data = await _meeting_tool._generate_summary(
        transcription.transcript,
        transcription.language or "zh",
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
    x_user_id: Optional[str] = Header(default="default"),
):
    """获取转录历史列表"""
    if _db is None:
        raise HTTPException(status_code=500, detail="会议 API 未初始化")

    transcriptions = _db.list_transcriptions(
        user_id=x_user_id or "default",
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
