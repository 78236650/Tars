"""Task 11: Evolution metrics API — 自进化指标对外可见。"""

from fastapi import APIRouter
from tars.evolution import EvolutionManager

router = APIRouter(prefix="/api/evolution", tags=["evolution"])
_mgr = EvolutionManager()


@router.get("/metrics")
def metrics(tenant_id: str = "default"):
    stats = _mgr.get_stats() if callable(getattr(_mgr, "get_stats", None)) else {}
    fb = _mgr.feedback_collector
    recent = fb.count_recent(tenant_id, days=7) if fb is not None else 0
    return {
        "stats": stats,
        "recent_feedback": recent,
    }
