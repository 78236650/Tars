"""P0 preflight: validate datasource connection + URL safety before profiling."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional

from ..bi.schema_explorer import SchemaExplorer
from ..utils.url_safety import validate_external_db_url

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    ok: bool
    reason: Optional[str] = None
    hint: Optional[str] = None


def run_preflight(connection_url: str) -> PreflightResult:
    try:
        validate_external_db_url(connection_url)
    except ValueError as e:
        return PreflightResult(
            ok=False,
            reason=f"connection_url rejected: {e}",
            hint="check scheme/host against TARS allow-list (set TARS_INSIGHT_ALLOW_PRIVATE_HOSTS=1 for dev)",
        )
    try:
        explorer = SchemaExplorer(connection_url)
        ok, msg = explorer.test_connection()
        if not ok:
            return PreflightResult(
                ok=False,
                reason=f"test_connection failed: {msg}",
                hint="verify credentials/host reachability",
            )
        return PreflightResult(ok=True)
    except Exception as e:
        logger.warning("[InsightForge] preflight error: %r", e)
        return PreflightResult(
            ok=False,
            reason=f"preflight error: {e}",
            hint="see backend logs",
        )
