# TARS Model Configuration API — Ollama + OpenAI-compatible endpoints
import logging
import os
import sqlite3
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tars.agent import Agent
from tars.database import Endpoint, EndpointStore
from tars.models import CustomProvider, OllamaProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["模型配置"])

_endpoint_store: Optional[EndpointStore] = None
_current_provider: Literal["ollama", "openai_compatible"] = "ollama"
_current_endpoint_id: Optional[str] = None


def init_endpoint_store(store: EndpointStore) -> None:
    global _endpoint_store
    _endpoint_store = store


def get_endpoint_store() -> EndpointStore:
    global _endpoint_store
    if _endpoint_store is None:
        from tars.database import Database

        _endpoint_store = EndpointStore(Database())
    return _endpoint_store


def _sync_llm_chain(agent: Agent) -> None:
    agent.dispatcher.set_provider(agent.provider)
    from tars.main import memory_manager

    memory_manager.set_provider(agent.provider)


def get_agent() -> Agent:
    from tars.main import agent

    return agent


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _normalize_model_ids(names: Optional[List[Any]]) -> List[str]:
    if not names:
        return []
    out: List[str] = []
    for x in names:
        if x is None:
            continue
        s = str(x).strip()
        if s:
            out.append(s)
    return out


def _endpoint_to_dict(ep: Endpoint) -> Dict[str, Any]:
    return {
        "id": ep.id,
        "name": ep.name,
        "base_url": ep.base_url,
        "api_key": ep.api_key or "",
        "models": list(ep.models or []),
        "enabled": ep.enabled,
        "created_at": ep.created_at,
        "updated_at": ep.updated_at,
    }


class SwitchModelRequest(BaseModel):
    provider: Literal["ollama", "openai_compatible"]
    model: str
    endpoint_id: Optional[str] = None


class EndpointCreate(BaseModel):
    name: str
    base_url: str
    api_key: Optional[str] = None


class EndpointUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    enabled: Optional[bool] = None


@router.get("/")
async def get_models_root() -> Dict[str, Any]:
    """聚合：Ollama 模型列表、端点列表、当前选择。"""
    agent = get_agent()
    store = get_endpoint_store()
    ollama_url = _ollama_base_url()
    ollama_models: List[str] = []
    ollama_status = "disconnected"
    try:
        op = OllamaProvider(base_url=ollama_url)
        ollama_models = await op.list_models()
        ollama_status = "connected"
    except Exception as e:
        logger.debug("Ollama list_models failed: %s", e)

    endpoints = [_endpoint_to_dict(ep) for ep in store.get_all()]

    return {
        "ollama_models": ollama_models,
        "ollama_base_url": ollama_url,
        "ollama_status": ollama_status,
        "endpoints": endpoints,
        "current": {
            "provider": _current_provider,
            "endpoint_id": _current_endpoint_id,
            "model": agent.current_model,
        },
    }


@router.get("/endpoints", response_model=List[Dict[str, Any]])
async def list_endpoints():
    store = get_endpoint_store()
    return [_endpoint_to_dict(ep) for ep in store.get_all()]


async def _try_fetch_models_for_endpoint(ep: Endpoint) -> Endpoint:
    store = get_endpoint_store()
    probe = ep.models[0] if ep.models else "gpt-3.5-turbo"
    try:
        prov = CustomProvider(base_url=ep.base_url, model=probe, api_key=ep.api_key)
        names = _normalize_model_ids(await prov.list_models())
        updated = store.update(ep.id, models=names)
        return updated or ep
    except Exception as e:
        logger.warning("fetch models failed for endpoint %s: %s", ep.id, e)
        return ep


@router.post("/endpoints", response_model=Dict[str, Any])
async def create_endpoint(body: EndpointCreate):
    store = get_endpoint_store()
    try:
        ep = store.create(name=body.name, base_url=body.base_url, api_key=body.api_key, models=[])
        ep = await _try_fetch_models_for_endpoint(ep)
        return _endpoint_to_dict(ep)
    except sqlite3.Error as e:
        logger.exception("create_endpoint: sqlite error")
        raise HTTPException(status_code=400, detail=f"数据库错误: {e}") from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_endpoint: unexpected error")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/endpoints/{endpoint_id}", response_model=Dict[str, Any])
async def update_endpoint(endpoint_id: str, body: EndpointUpdate):
    store = get_endpoint_store()
    existing = store.get_by_id(endpoint_id)
    if not existing:
        raise HTTPException(status_code=404, detail="端点不存在")
    data = body.model_dump(exclude_unset=True)
    ep = store.update(endpoint_id, **data)
    if not ep:
        raise HTTPException(status_code=404, detail="端点不存在")
    return _endpoint_to_dict(ep)


@router.delete("/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: str):
    global _current_endpoint_id, _current_provider
    store = get_endpoint_store()
    if not store.get_by_id(endpoint_id):
        raise HTTPException(status_code=404, detail="端点不存在")
    store.delete(endpoint_id)
    if _current_endpoint_id == endpoint_id:
        _current_endpoint_id = None
        _current_provider = "ollama"
        agent = get_agent()
        try:
            agent.switch_model(os.getenv("OLLAMA_MODEL", "llama3.2"))
            _sync_llm_chain(agent)
        except Exception:
            pass
    return {"success": True}


@router.post("/endpoints/{endpoint_id}/fetch-models", response_model=Dict[str, Any])
async def fetch_endpoint_models(endpoint_id: str):
    store = get_endpoint_store()
    ep = store.get_by_id(endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="端点不存在")
    before = list(ep.models or [])
    ep = await _try_fetch_models_for_endpoint(ep)
    return {
        "success": True,
        "models": ep.models or [],
        "changed": (ep.models or []) != before,
    }


@router.post("/endpoints/{endpoint_id}/test", response_model=Dict[str, Any])
async def test_endpoint(endpoint_id: str):
    store = get_endpoint_store()
    ep = store.get_by_id(endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="端点不存在")
    probe = ep.models[0] if ep.models else "gpt-3.5-turbo"
    prov = CustomProvider(base_url=ep.base_url, model=probe, api_key=ep.api_key)
    success, message = await prov.test_connection()
    return {"success": success, "message": message}


@router.post("/switch", response_model=Dict[str, Any])
async def switch_model(request: SwitchModelRequest):
    global _current_provider, _current_endpoint_id
    agent = get_agent()

    if request.provider == "ollama":
        ok = agent.switch_model(request.model)
        if not ok:
            raise HTTPException(status_code=400, detail=f"无法切换到模型: {request.model}")
        _current_provider = "ollama"
        _current_endpoint_id = None
        _sync_llm_chain(agent)
        return {
            "success": True,
            "message": f"已切换到 Ollama: {request.model}",
            "current": {
                "provider": _current_provider,
                "endpoint_id": _current_endpoint_id,
                "model": agent.current_model,
            },
        }

    if request.provider == "openai_compatible":
        if not request.endpoint_id:
            raise HTTPException(status_code=400, detail="openai_compatible 需要 endpoint_id")
        store = get_endpoint_store()
        ep = store.get_by_id(request.endpoint_id)
        if not ep:
            raise HTTPException(status_code=404, detail="端点不存在")
        if not ep.enabled:
            raise HTTPException(status_code=400, detail="端点已禁用")
        try:
            agent.provider = CustomProvider(
                base_url=ep.base_url,
                model=request.model,
                api_key=ep.api_key,
            )
            agent.current_model = request.model
            agent.dispatcher.set_provider(agent.provider)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"切换失败: {e}") from e
        _current_provider = "openai_compatible"
        _current_endpoint_id = request.endpoint_id
        _sync_llm_chain(agent)
        return {
            "success": True,
            "message": f"已切换到 {ep.name}: {request.model}",
            "current": {
                "provider": _current_provider,
                "endpoint_id": _current_endpoint_id,
                "model": agent.current_model,
            },
        }

    raise HTTPException(status_code=400, detail="不支持的 provider")
