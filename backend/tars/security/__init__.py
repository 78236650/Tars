# TARS Security Module — v4.0.0 Phase 1
# Cross-cutting security services: sanitization, audit, injection guard, memory permission.
from .patterns import SENSITIVE_PATTERNS, match_sensitive  # noqa: F401
from .sanitizer import Sanitizer, sanitizer  # noqa: F401
from .audit import AuditLogger, audit_logger, init_audit_logger  # noqa: F401
from .audit import client_ip_from_request, safe_audit  # noqa: F401
from .injection_guard import InjectionGuard, injection_guard, detect_injection  # noqa: F401
from .memory_permission import MemoryPermission, MemoryScope, memory_permission, init_memory_permission  # noqa: F401
from .tool_permission import ToolPermissionChecker, tool_permission_checker  # noqa: F401

__all__ = [
    "SENSITIVE_PATTERNS",
    "match_sensitive",
    "Sanitizer",
    "sanitizer",
    "AuditLogger",
    "audit_logger",
    "init_audit_logger",
    "client_ip_from_request",
    "safe_audit",
    "InjectionGuard",
    "injection_guard",
    "detect_injection",
    "MemoryPermission",
    "MemoryScope",
    "memory_permission",
    "init_memory_permission",
    "ToolPermissionChecker",
    "tool_permission_checker",
]
