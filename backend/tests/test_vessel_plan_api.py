import asyncio

from tars.api._auth import Principal
from tars.api.vessel_plan_routes import get_horizon, init_vessel_plan_api, optimize_plan
from tars.api.vessel_plan_routes import OptimizeRequest
from tars.database.base import Database


def _principal(admin=False):
    return Principal(
        user_id="default",
        tenant_id="default",
        role="admin" if admin else "user",
        is_admin=admin,
        role_template_id="",
        api_key="test",
    )


def test_horizon_auto_seeds():
    db = Database(":memory:")
    init_vessel_plan_api(db)
    result = asyncio.run(get_horizon(hours=48, principal=_principal()))
    assert len(result["berths"]) == 6
    assert len(result["rows"]) >= 8


def test_optimize_returns_summary():
    db = Database(":memory:")
    init_vessel_plan_api(db)
    result = asyncio.run(
        optimize_plan(body=OptimizeRequest(horizon_hours=48), principal=_principal())
    )
    assert result["agent_summary"]
    assert result["total_wait_min"] >= 0
