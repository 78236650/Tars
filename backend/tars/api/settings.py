"""系统设置 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ._auth import require_authenticated_user, require_admin, Principal

router = APIRouter(prefix="/api/settings", tags=["Settings"])

_embedding_manager = None


def init_settings_api(embedding_manager) -> None:
    global _embedding_manager
    _embedding_manager = embedding_manager


class EmbeddingConfigRequest(BaseModel):
    provider: str
    model: str


@router.get("/embedding")
async def get_embedding_config(
    principal: Principal = Depends(require_authenticated_user),
):
    if _embedding_manager is None:
        raise HTTPException(status_code=500, detail="设置 API 未初始化")
    return _embedding_manager.get_info()


@router.put("/embedding")
async def update_embedding_config(
    request: EmbeddingConfigRequest,
    principal: Principal = Depends(require_admin),
):
    if _embedding_manager is None:
        raise HTTPException(status_code=500, detail="设置 API 未初始化")
    result = _embedding_manager.reinitialize(request.provider, request.model)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
