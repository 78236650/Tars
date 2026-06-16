"""TARS API - 视频生成状态查询"""
from fastapi import APIRouter, HTTPException
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tars.generation import AgnesProvider

router = APIRouter(prefix="/api/generation", tags=["生成服务"])

# 弱引用到启动时创建的 provider
_gen_provider = None


def init_generation_api(provider):
    global _gen_provider
    _gen_provider = provider


@router.get("/video/{task_id}")
async def get_video_status(task_id: str):
    """查询视频生成任务状态"""
    if _gen_provider is None:
        raise HTTPException(status_code=503, detail="视频生成服务未配置")
    result = await _gen_provider.poll_video(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "url": result.url,
        "error": result.error,
        "metadata": result.metadata,
    }
