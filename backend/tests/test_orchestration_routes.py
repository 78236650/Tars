import asyncio

from tars.api._auth import Principal
from tars.api.orchestration_routes import get_orchestration_task, init_orchestration_api, list_orchestration_tasks
from tars.database.base import Database
from tars.orchestration.orchestration_memory import OrchestrationMemory


def test_list_orchestration_tasks_api():
    db = Database(":memory:")
    om = OrchestrationMemory(db=db, tenant_id="default")
    tid = om.start_task(session_id="s1", goal="安排 COSCO123 靠泊")
    om.record_output(tid, agent_type="research", subtask="查泊位", output="3号空闲")
    om.finish_task(tid)

    init_orchestration_api(db)
    principal = Principal(
        user_id="default",
        tenant_id="default",
        role="user",
        is_admin=False,
        role_template_id="",
        api_key="test",
    )
    result = asyncio.run(list_orchestration_tasks(principal=principal))
    assert result["total"] == 1
    assert result["tasks"][0]["goal"] == "安排 COSCO123 靠泊"


def test_get_orchestration_task_detail():
    db = Database(":memory:")
    om = OrchestrationMemory(db=db, tenant_id="default")
    tid = om.start_task(session_id="s1", goal="并行调度")
    om.record_output(tid, agent_type="plan", subtask="规划", output="步骤1")
    om.set_shared(tid, "berth", {"id": "3"}, by="plan")

    init_orchestration_api(db)
    principal = Principal(
        user_id="default",
        tenant_id="default",
        role="user",
        is_admin=False,
        role_template_id="",
        api_key="test",
    )
    detail = asyncio.run(get_orchestration_task(task_id=tid, principal=principal))
    assert detail["task"]["goal"] == "并行调度"
    assert len(detail["outputs"]) == 1
    assert detail["shared"]["berth"]["id"] == "3"


def test_dispatch_orchestration_api():
    db = Database(":memory:")
    init_orchestration_api(db)
    from tars.api.orchestration_routes import DispatchRequest, dispatch_orchestration

    principal = Principal(
        user_id="default",
        tenant_id="default",
        role="user",
        is_admin=False,
        role_template_id="",
        api_key="test",
    )
    result = asyncio.run(dispatch_orchestration(
        payload=DispatchRequest(session_id="s1", goal="安排COSCO123靠3号泊位卸800箱"),
        principal=principal,
    ))
    assert result["status"] == "done"
    assert len(result["outputs"]) >= 2
