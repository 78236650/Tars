"""Structured logging configuration (TARS v5.0.5 / P1).

Single entry point ``setup_logging()`` installs a process-wide logging config
via ``dictConfig``. A custom filter injects the request-scoped ``trace_id``
(populated by ``TraceIDMiddleware`` in v5.0.5/P2) into every record so logs
from the same request can be correlated.

Set ``TARS_LOG_LEVEL`` (default INFO) and ``TARS_LOG_JSON`` (``1`` for JSON
lines, otherwise human-readable text) to control output.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict


class TraceIdFilter(logging.Filter):
    """Attach the current request's trace_id to each log record.

    Reads lazily from ``tars.context`` so this module has no import-time
    dependency on the context var (avoids circular import during startup).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            trace_id = "-"
            try:
                from .context import get_current_trace_id

                trace_id = get_current_trace_id() or "-"
            except Exception:
                trace_id = "-"
            record.trace_id = trace_id
        return True


_TEXT_FORMAT = "%(asctime)s %(levelname)-7s [%(trace_id)s] %(name)s: %(message)s"
_JSON_FORMAT = (
    '{"ts":"%(asctime)s","level":"%(levelname)s","trace_id":"%(trace_id)s",'
    '"logger":"%(name)s","msg":"%(message)s"}'
)

_configured = False


def setup_logging(level: str | None = None, json_mode: bool | None = None) -> None:
    """Install process-wide logging. Idempotent — safe to call once at startup.

    Honors ``TARS_LOG_LEVEL`` and ``TARS_LOG_JSON`` when args are omitted.
    """
    global _configured
    if _configured:
        return

    resolved_level = (level or os.getenv("TARS_LOG_LEVEL", "INFO")).upper()
    if json_mode is None:
        json_mode = os.getenv("TARS_LOG_JSON", "0").strip() in ("1", "true", "True")
    fmt = _JSON_FORMAT if json_mode else _TEXT_FORMAT

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "trace_id": {"()": "tars.logging_config.TraceIdFilter"},
        },
        "formatters": {
            "tars": {"format": fmt, "datefmt": "%Y-%m-%d %H:%M:%S"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "tars",
                "filters": ["trace_id"],
                "stream": "ext://sys.stdout",
            },
        },
        "root": {"level": resolved_level, "handlers": ["console"]},
        "loggers": {
            # Tame noisy third-party loggers.
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "chromadb": {"level": "WARNING"},
        },
    }

    import logging.config

    logging.config.dictConfig(config)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor mirroring ``logging.getLogger``."""
    return logging.getLogger(name)

