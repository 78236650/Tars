import asyncio
import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from ..channels.base import Channel, ChannelMessage
from ..tenant.context import TenantContextCache


router = APIRouter(prefix="/api", tags=["invoke"])

_agent = None
_tenant_cache: Optional[TenantContextCache] = None
_memory_manager = None
_user_store = None
_pipeline_engine = None


def init_invoke_api(agent, tenant_cache: TenantContextCache, memory_manager, user_store=None, pipeline_engine=None) -> None:
    global _agent, _tenant_cache, _memory_manager, _user_store, _pipeline_engine
    _agent = agent
    _tenant_cache = tenant_cache
    _memory_manager = memory_manager
    _user_store = user_store
    _pipeline_engine = pipeline_engine


def _extract_api_key(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip() or None
    return value or None


class InvokeRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    pipeline: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class InMemoryInvokeChannel(Channel):
    def __init__(self):
        self.events: list[dict[str, Any]] = []

    async def receive(self, raw_message: Any) -> ChannelMessage:
        raise NotImplementedError("invoke channel does not support receive")

    async def send(self, session_id: str, event: dict) -> None:
        self.events.append(event)

    async def stream(self, session_id: str, chunk: str) -> None:
        self.events.append(
            {
                "type": "text_chunk",
                "session_id": session_id,
                "content": chunk,
            }
        )

    def build_response(self, session_id: str) -> dict[str, Any]:
        text_parts = [event.get("content", "") for event in self.events if event.get("type") == "text_chunk"]
        done_event = next((event for event in reversed(self.events) if event.get("type") == "done"), {})
        return {
            "response": "".join(text_parts),
            "session_id": session_id,
            "tool_calls": [],
            "usage": {"model": done_event.get("model")},
        }


class StreamingInvokeChannel(Channel):
    def __init__(self):
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def receive(self, raw_message: Any) -> ChannelMessage:
        raise NotImplementedError("invoke channel does not support receive")

    async def send(self, session_id: str, event: dict) -> None:
        await self.queue.put(event)

    async def stream(self, session_id: str, chunk: str) -> None:
        await self.queue.put(
            {
                "type": "text_chunk",
                "session_id": session_id,
                "content": chunk,
            }
        )


def _to_sse(event: dict[str, Any]) -> str:
    event_type = event.get("type", "message")
    return f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/invoke")
async def invoke(
    payload: InvokeRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
    authorization: Optional[str] = Header(default=None),
):
    if _tenant_cache is None or _memory_manager is None:
        raise HTTPException(status_code=500, detail="invoke api not initialized")

    user = None
    api_key = _extract_api_key(authorization)
    if _user_store is not None:
        if not api_key:
            raise HTTPException(status_code=401, detail="未提供 API Key")
        user = _user_store.get_user_by_api_key(api_key)
        if user is None:
            raise HTTPException(status_code=401, detail="无效的 API Key")

    from ..org import ORG_ID

    # v5.0: single org — machine invoke always uses org scope; X-Tenant-Id ignored.
    tenant_id = ORG_ID

    session_id = payload.session_id or str(uuid.uuid4())
    tenant_context = _tenant_cache.get_or_create(
        tenant_id,
        lambda current_tenant: _memory_manager.for_tenant(current_tenant),
        session_id=session_id,
        metadata=payload.context,
    )

    if payload.pipeline:
        if _pipeline_engine is None:
            raise HTTPException(status_code=400, detail="pipeline engine not initialized")
        if payload.stream:
            raise HTTPException(status_code=501, detail="pipeline stream not implemented yet")
        if _agent is not None:
            _pipeline_engine.provider = _agent.provider
        try:
            pipeline_result = await _pipeline_engine.execute(
                payload.pipeline,
                {
                    "message": payload.message,
                    "session_id": session_id,
                    "tenant_id": tenant_id,
                    **payload.context,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "response": pipeline_result["final_output"],
            "session_id": session_id,
            "tool_calls": [],
            "usage": {"model": getattr(getattr(_pipeline_engine, "provider", None), "model", None)},
            "pipeline": pipeline_result["pipeline"],
            "pipeline_outputs": pipeline_result["outputs"],
        }

    if _agent is None:
        raise HTTPException(status_code=500, detail="invoke agent not initialized")

    if payload.stream:
        channel = StreamingInvokeChannel()

        async def event_generator():
            task = asyncio.create_task(
                _agent.handle_message(
                    session_id=session_id,
                    user_content=payload.message,
                    channel=channel,
                    file_ids=None,
                    tenant_context=tenant_context,
                    request_context={
                        "transport": "rest",
                        "authorization": authorization,
                        "user_id": getattr(user, "id", None),
                        "user_role": getattr(user, "role", "user").value if hasattr(getattr(user, "role", None), "value") else "user",
                        "stream": True,
                    },
                )
            )
            try:
                while True:
                    event = await channel.queue.get()
                    yield _to_sse(event)
                    if event.get("type") in {"done", "error"}:
                        break
            finally:
                await task

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    channel = InMemoryInvokeChannel()
    await _agent.handle_message(
        session_id=session_id,
        user_content=payload.message,
        channel=channel,
        file_ids=None,
        tenant_context=tenant_context,
        request_context={
            "transport": "rest",
            "authorization": authorization,
            "user_id": getattr(user, "id", None),
            "user_role": getattr(user, "role", "user").value if hasattr(getattr(user, "role", None), "value") else "user",
            "stream": payload.stream,
        },
    )
    return channel.build_response(session_id)
