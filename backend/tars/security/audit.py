"""Audit logger — v4.0.0 Phase 1.

Writes structured audit records for security-relevant operations:
tool calls, memory access, config changes, permission denials, etc.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def client_ip_from_request(request) -> str:
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = getattr(request, "client", None)
    if client and getattr(client, "host", None):
        return client.host
    return ""


def safe_audit(callback: Callable[["AuditLogger"], None]) -> None:
    """Run an audit callback when the global logger is available."""
    try:
        if audit_logger:
            callback(audit_logger)
    except Exception:
        pass


class AuditLogger:
    """Persistent audit trail for compliance and intrusion detection."""

    def __init__(self, db):
        self._db = db

    def log(
        self,
        action: str,
        resource_type: str,
        tenant_id: str = "default",
        user_id: str = "default",
        resource_id: str = "",
        detail: str = "",
        client_ip: str = "",
    ):
        """Write one audit entry. Non-blocking — failures are logged to stderr."""
        try:
            self._db.add_audit_log(
                action=action,
                resource_type=resource_type,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_id=resource_id,
                detail=str(detail)[:2000],
                client_ip=client_ip,
            )
        except Exception as exc:
            import sys
            print(f"[AuditLogger] Failed to write audit log: {exc}", file=sys.stderr)

    # ── convenience methods ────────────────────────────────────────

    def log_tool_call(
        self,
        tool_name: str,
        tenant_id: str = "default",
        user_id: str = "default",
        arguments: Optional[dict] = None,
        success: bool = True,
        client_ip: str = "",
    ):
        detail = json.dumps(arguments or {}, ensure_ascii=False, default=str)
        try:
            from .sanitizer import sanitizer
            detail = sanitizer.sanitize(detail)
        except Exception:
            pass
        self.log(
            action=f"tool_call:{'success' if success else 'failed'}",
            resource_type="tool",
            resource_id=tool_name,
            tenant_id=tenant_id,
            user_id=user_id,
            detail=detail,
            client_ip=client_ip,
        )

    def log_permission_denied(
        self,
        resource: str,
        resource_type: str,
        tenant_id: str = "default",
        user_id: str = "default",
        reason: str = "",
        client_ip: str = "",
    ):
        self.log(
            action="permission_denied",
            resource_type=resource_type,
            resource_id=resource,
            tenant_id=tenant_id,
            user_id=user_id,
            detail=reason,
            client_ip=client_ip,
        )

    def log_memory_access(
        self,
        memory_id: str,
        action: str,
        tenant_id: str = "default",
        user_id: str = "default",
        client_ip: str = "",
    ):
        self.log(
            action=f"memory:{action}",
            resource_type="memory",
            resource_id=memory_id,
            tenant_id=tenant_id,
            user_id=user_id,
            client_ip=client_ip,
        )

    def log_model_call(
        self,
        model_name: str,
        tenant_id: str = "default",
        user_id: str = "default",
        token_count: int = 0,
        client_ip: str = "",
    ):
        self.log(
            action="model_call",
            resource_type="model",
            resource_id=model_name,
            tenant_id=tenant_id,
            user_id=user_id,
            detail=f"tokens={token_count}",
            client_ip=client_ip,
        )

    def log_login(
        self,
        user_id: str = "default",
        tenant_id: str = "default",
        success: bool = True,
        detail: str = "",
        client_ip: str = "",
    ):
        self.log(
            action="login" if success else "login:failed",
            resource_type="auth",
            resource_id=user_id or "unknown",
            tenant_id=tenant_id or user_id or "default",
            user_id=user_id or "unknown",
            detail=detail,
            client_ip=client_ip,
        )

    def log_user_event(
        self,
        action: str,
        target_user_id: str,
        actor_id: str = "default",
        tenant_id: str = "default",
        detail: str = "",
        client_ip: str = "",
    ):
        self.log(
            action=action,
            resource_type="user",
            resource_id=target_user_id,
            tenant_id=tenant_id,
            user_id=actor_id,
            detail=detail,
            client_ip=client_ip,
        )

    def log_session_event(
        self,
        action: str,
        session_id: str,
        tenant_id: str = "default",
        user_id: str = "default",
        detail: str = "",
        client_ip: str = "",
    ):
        self.log(
            action=action,
            resource_type="session",
            resource_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            detail=detail,
            client_ip=client_ip,
        )

    def log_config_change(
        self,
        resource_id: str,
        tenant_id: str = "default",
        user_id: str = "default",
        detail: str = "",
        client_ip: str = "",
    ):
        self.log(
            action="config_change",
            resource_type="config",
            resource_id=resource_id,
            tenant_id=tenant_id,
            user_id=user_id,
            detail=detail,
            client_ip=client_ip,
        )

    def log_skill_event(
        self,
        action: str,
        skill_id: str,
        tenant_id: str = "default",
        user_id: str = "default",
        detail: str = "",
        client_ip: str = "",
    ):
        self.log(
            action=action,
            resource_type="skill",
            resource_id=skill_id,
            tenant_id=tenant_id,
            user_id=user_id,
            detail=detail,
            client_ip=client_ip,
        )

    def list(
        self,
        tenant_id: str = "",
        user_id: str = "",
        action: str = "",
        resource_type: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list, int]:
        return self._db.list_audit_logs(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            page=page,
            page_size=page_size,
        )


# ── Global singleton ────────────────────────────────────────────────

audit_logger: Optional[AuditLogger] = None


def init_audit_logger(db) -> AuditLogger:
    global audit_logger
    audit_logger = AuditLogger(db)
    return audit_logger
