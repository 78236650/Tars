"""LLM provider fallback chain — v4.1.0"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import ChatMessage, ProviderBase


class RetryableError(Exception):
    """Marked retryable provider failure."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class AllProvidersFailedError(Exception):
    pass


def is_retryable(exc: BaseException, retry_on: Optional[List[Any]] = None) -> bool:
    if isinstance(exc, RetryableError):
        return True

    retry_on = retry_on or [429, 500, 502, 503, 504, "timeout"]
    codes = {x for x in retry_on if isinstance(x, int)}
    keywords = {str(x).lower() for x in retry_on if not isinstance(x, int)}

    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status in codes:
        return True

    try:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            if exc.response.status_code in codes:
                return True
    except ImportError:
        pass

    msg = str(exc).lower()
    return any(k in msg for k in keywords)


def _record_usage(
    db,
    tenant_id: str,
    provider: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    user_id: str = "",
) -> None:
    if not db:
        return
    try:
        db.record_provider_usage(
            tenant_id=tenant_id,
            provider=provider,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            user_id=user_id,
        )
    except Exception:
        pass


def _log_fallback(from_provider: str, to_provider: str, reason: str, tenant_id: str = "default") -> None:
    try:
        from ..security.audit import audit_logger
        if audit_logger:
            audit_logger.log_model_fallback(from_provider, to_provider, reason, tenant_id=tenant_id)
    except Exception:
        pass


async def chat_with_fallback(
    *,
    primary: ProviderBase,
    providers: Dict[str, ProviderBase],
    fallback_cfg: Dict[str, Any],
    messages: List[ChatMessage],
    stream: bool = False,
    model: str | None = None,
    tenant_id: str = "default",
    user_id: str = "",
    db=None,
    primary_name: str = "default",
    **kwargs,
):
    """Try primary provider, then configured fallback chain."""
    if not fallback_cfg.get("enabled"):
        response = await primary.chat(messages, stream=stream, model=model, **kwargs)
        _record_usage(db, tenant_id, primary_name, model or getattr(primary, "model", "") or "", user_id=user_id)
        return response

    retry_on = fallback_cfg.get("retry_on")
    max_attempts = int(fallback_cfg.get("max_attempts", 3))

    attempts: List[tuple] = [(primary_name, primary, model)]
    for entry in fallback_cfg.get("chain", []):
        pname = entry.get("provider", "")
        prov = providers.get(pname)
        if prov and prov is not primary:
            attempts.append((pname, prov, entry.get("model")))

    last_error: Optional[BaseException] = None
    prev_name: Optional[str] = None

    for idx, (name, prov, use_model) in enumerate(attempts[:max_attempts]):
        try:
            response = await prov.chat(
                messages,
                stream=stream,
                model=use_model or model,
                **kwargs,
            )
            usage = getattr(response, "usage", None) or {}
            _record_usage(
                db,
                tenant_id,
                name,
                use_model or model or getattr(prov, "model", "") or "",
                int(usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0) or 0),
                int(usage.get("completion_tokens", 0) or usage.get("output_tokens", 0) or 0),
                user_id=user_id,
            )
            return response
            _record_usage(
                db,
                tenant_id,
                name,
                use_model or model or getattr(prov, "model", "") or "",
                int(usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0) or 0),
                int(usage.get("completion_tokens", 0) or usage.get("output_tokens", 0) or 0),
                user_id=user_id,
            )
            return response
        except Exception as exc:
            last_error = exc
            if prev_name and name != prev_name:
                _log_fallback(prev_name, name, str(exc), tenant_id=tenant_id)
            prev_name = name
            if idx + 1 >= len(attempts[:max_attempts]) or not is_retryable(exc, retry_on):
                break

    if last_error:
        raise AllProvidersFailedError(str(last_error)) from last_error
    raise AllProvidersFailedError("No providers available")


class FallbackProviderWrapper:
    """Transparent wrapper applying fallback chain on chat()."""

    def __init__(
        self,
        primary: ProviderBase,
        providers: Dict[str, ProviderBase],
        fallback_cfg: Dict[str, Any],
        primary_name: str = "default",
        db=None,
    ):
        self._primary = primary
        self._providers = providers
        self._fallback_cfg = fallback_cfg
        self._primary_name = primary_name
        self._db = db

    async def chat(self, messages, stream=False, model=None, tenant_id: str = "default", user_id: str = "", **kwargs):
        return await chat_with_fallback(
            primary=self._primary,
            providers=self._providers,
            fallback_cfg=self._fallback_cfg,
            messages=messages,
            stream=stream,
            model=model,
            tenant_id=tenant_id,
            user_id=user_id,
            db=self._db,
            primary_name=self._primary_name,
            **kwargs,
        )

    async def list_models(self):
        return await self._primary.list_models()

    def __getattr__(self, name: str):
        return getattr(self._primary, name)


def wrap_provider_with_fallback(
    primary: ProviderBase,
    providers: Dict[str, ProviderBase],
    fallback_cfg: Dict[str, Any],
    primary_name: str = "default",
    db=None,
) -> ProviderBase:
    if not fallback_cfg.get("enabled"):
        return primary
    return FallbackProviderWrapper(primary, providers, fallback_cfg, primary_name, db)
