"""Field-level encryption for sensitive values at rest (TARS v5.0.5 / P6).

API keys were stored in plaintext. This module provides:
- ``encrypt(value)`` / ``decrypt(token)`` — reversible Fernet encryption, so a
  value can still be shown to its owner (e.g. returned on login).
- ``lookup_hash(value)`` — a deterministic keyed HMAC for indexed equality
  lookups (Fernet ciphertext is non-deterministic and can't be matched with
  ``WHERE col = ?``).

The key is derived from ``TARS_ENCRYPTION_KEY`` if set, else from
``TARS_JWT_SECRET`` (so existing deployments work without new config). In
production both being unset raises; in dev a fixed fallback is used with a
warning. Decryption of a legacy plaintext value (not a valid token) returns it
unchanged, so migration is non-destructive.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("tars.crypto")

_DEV_FALLBACK = "dev-only-insecure-encryption-secret-change-me"


def _secret() -> str:
    secret = (
        os.environ.get("TARS_ENCRYPTION_KEY", "").strip()
        or os.environ.get("TARS_JWT_SECRET", "").strip()
    )
    if secret:
        return secret
    if os.environ.get("TARS_ENV", "").lower() == "production":
        raise RuntimeError(
            "TARS_ENCRYPTION_KEY or TARS_JWT_SECRET required in production for field encryption"
        )
    logger.warning("[crypto] no encryption secret set; using DEV fallback (insecure)")
    return _DEV_FALLBACK


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        # Derive a stable 32-byte Fernet key from the secret.
        digest = hashlib.sha256(_secret().encode("utf-8")).digest()
        _fernet = Fernet(base64.urlsafe_b64encode(digest))
    return _fernet


_TOKEN_PREFIX = "enc::"


class DecryptionError(Exception):
    """Raised when a value carries the ``enc::`` prefix but cannot be decrypted.

    This means the encryption secret is wrong/missing or the ciphertext is
    corrupt. Callers must treat this as "the value is unavailable" — never fall
    back to the ciphertext itself, which would leak a non-functional token into
    places that expect plaintext (e.g. an API key sent to an LLM provider).
    """


def encrypt(value: str) -> str:
    """Encrypt a plaintext value. Returns a prefixed token for round-tripping."""
    if value is None:
        return value
    token = _get_fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return _TOKEN_PREFIX + token


def decrypt(token: str) -> str:
    """Decrypt a token produced by ``encrypt``.

    A value without the ``enc::`` prefix (legacy plaintext) is returned
    unchanged so the migration can run lazily and old rows keep working.

    A prefixed value that fails to decrypt raises :class:`DecryptionError`
    rather than returning the ciphertext as-is — returning the unusable token
    silently is worse than failing loudly, because it gets mistaken for a real
    plaintext secret downstream.
    """
    if token is None or not token.startswith(_TOKEN_PREFIX):
        return token
    raw = token[len(_TOKEN_PREFIX):]
    try:
        return _get_fernet().decrypt(raw.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        logger.error("[crypto] decrypt failed: wrong secret or corrupt ciphertext")
        raise DecryptionError(
            "failed to decrypt value: wrong encryption secret or corrupt data"
        ) from e


def decrypt_or_none(token: str) -> Optional[str]:
    """Like :func:`decrypt`, but returns ``None`` on decryption failure.

    For call sites that prefer a missing value over an exception (e.g. listing
    users where one bad row shouldn't fail the whole query). The result is
    never the ciphertext.
    """
    try:
        return decrypt(token)
    except DecryptionError:
        return None


def is_encrypted(value: str) -> bool:
    return bool(value) and value.startswith(_TOKEN_PREFIX)


def lookup_hash(value: str) -> str:
    """Deterministic keyed HMAC for indexed equality lookups."""
    if value is None:
        return value
    return hmac.new(
        _secret().encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()

