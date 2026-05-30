"""Persisted JWT access tokens (jti revocation registry)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union

from .models import get_local_now


class AuthTokenStore:
    """auth_tokens table: track issued JTIs for revocation."""

    def __init__(self, db):
        self.db = db

    def insert_token(
        self,
        jti: str,
        user_id: str,
        expires_at: Union[datetime, float, int],
    ) -> None:
        if isinstance(expires_at, (int, float)):
            expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        else:
            expires_dt = expires_at
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO auth_tokens (id, user_id, expires_at, revoked, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (jti, user_id, expires_dt, get_local_now()),
        )
        conn.commit()

    def revoke_token(self, jti: str) -> None:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE auth_tokens SET revoked = 1 WHERE id = ?",
            (jti,),
        )
        conn.commit()

    def is_token_revoked(self, jti: str) -> bool:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT revoked FROM auth_tokens WHERE id = ?",
            (jti,),
        )
        row = cursor.fetchone()
        if row is None:
            return False
        return bool(row[0])
