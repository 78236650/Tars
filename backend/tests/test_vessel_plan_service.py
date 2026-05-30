from tars.database.base import Database
from tars.vessel_plan.seed import seed_demo_port
from tars.vessel_plan.service import VesselPlanService


def test_optimize_writes_assignments():
    db = Database(":memory:")
    seed_demo_port(db)
    svc = VesselPlanService(db, tenant_id="default")
    result = svc.optimize(horizon_hours=48)
    assert result["total_wait_min"] >= 0
    assert len(result["rows"]) >= 8
    assert result["agent_summary"]
