import asyncio

from tars.api._auth import Principal
from tars.api.orchestration_routes import init_orchestration_api, list_orchestration_tasks
from tars.api.vessel_plan_routes import AdoptRequest, adopt_plans, init_vessel_plan_api, optimize_plan
from tars.api.vessel_plan_routes import OptimizeRequest
from tars.database.base import Database


def test_adopt_creates_orchestration_task():
    db = Database(":memory:")
    init_orchestration_api(db)
    init_vessel_plan_api(db)
    principal = Principal(
        user_id="default",
        tenant_id="default",
        role="user",
        is_admin=False,
        role_template_id="",
        api_key="test",
    )
    opt = asyncio.run(
        optimize_plan(body=OptimizeRequest(horizon_hours=48), principal=principal)
    )
    first_id = opt["rows"][0]["voyage_id"]
    adopt = asyncio.run(
        adopt_plans(
            body=AdoptRequest(voyage_ids=[first_id], session_id="s-demo"),
            principal=principal,
        )
    )
    assert adopt["count"] >= 1
    tasks = asyncio.run(list_orchestration_tasks(principal=principal))
    assert tasks["total"] >= 1
