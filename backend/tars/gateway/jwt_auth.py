"""JWT access token issuance and validation (TARS v5.0).

HS256 tokens carry ``sub`` (user_id), ``org_id``, ``jti``, and ``exp``.
Secret from ``TARS_JWT_SECRET``; production must set it (no fallback).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

from ..org import ORG_ID

_ALGORITHM = "HS256"
_DEV_FALLBACK_SECRET = "dev-only-tars-jwt-secret-not-for-production"
_DEFAULT_ACCESS_HOURS = 24


def _is_production() -> bool:
    env = (
        os.environ.get("TARS_ENV")
        or os.environ.get("ENV")
        or os.environ.get("NODE_ENV")
        or ""
    ).lower()
    return env in ("production", "prod")


def get_jwt_secret() -> str:
    """Resolve signing secret. Raises if missing in production."""
    secret = os.environ.get("TARS_JWT_SECRET", "").strip()
    if secret:
        return secret
    if _is_production():
        raise RuntimeError("TARS_JWT_SECRET is required in production")
    print(
        "[JWT] WARNING: TARS_JWT_SECRET 未设置，使用仅供开发的回退密钥；"
        "切勿在生产环境使用。"
    )
    return _DEV_FALLBACK_SECRET


def _access_token_lifetime() -> timedelta:
    raw = os.environ.get("TARS_JWT_ACCESS_HOURS", "").strip()
    if raw:
        try:
            hours = float(raw)
        except ValueError:
            hours = _DEFAULT_ACCESS_HOURS
    else:
        hours = _DEFAULT_ACCESS_HOURS
    return timedelta(hours=hours)


def create_access_token(user_id: str) -> str:
    """Issue a signed access token for ``user_id``."""
    now = datetime.now(timezone.utc)
    exp = now + _access_token_lifetime()
    payload = {
        "sub": user_id,
        "org_id": ORG_ID,
        "jti": str(uuid.uuid4()),
        "exp": exp,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Validate and decode an access token. Raises ``jwt`` exceptions on failure."""
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[_ALGORITHM],
        options={"require": ["sub", "org_id", "exp", "jti"]},
    )
