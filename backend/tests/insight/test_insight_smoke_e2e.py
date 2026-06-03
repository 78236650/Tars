"""Full-stack smoke tests — TARS main FastAPI app + seeded case_orders_shop.

Run:
  pytest -m insight_smoke tests/insight/test_insight_smoke_e2e.py -v
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Tuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tars.database import Database, UserStore
from tars.database.user_store import UserRole
from tars.api._auth import Principal
from tars.insight.api.router import _require as insight_require, init_insight_api
from tars.insight.job_runner import InsightJobRunner
from tars.modules.registry import module_registry

from tests.insight.case_orders_shop import USER_ID, seed
from tests.insight.conftest import _qa_engine_factory
from tests.insight.suite_runner import load_suite_cases, run_smoke_steps

_SMOKE_CASES = load_suite_cases(layers=["smoke"])


def _skip_if_insight_unavailable(client: TestClient) -> None:
    res = client.get("/api/insight/version", headers={"X-API-Key": "probe"})
    if res.status_code == 503:
        pytest.skip("insight module disabled or dependencies missing in modules.yaml")
    if res.status_code == 404:
        pytest.skip("insight router not mounted on main app")


@pytest.fixture(scope="module")
def tars_smoke_stack(tmp_path_factory) -> Tuple[TestClient, Any, Dict[str, str]]:
    """Swap main app DB for isolated sqlite, seed case tenant, return client + headers."""
    import tars.api._auth as auth_mod
    import tars.main as main

    db_path = tmp_path_factory.mktemp("insight_smoke") / "tars.db"
    smoke_db = Database(str(db_path))

    main.db = smoke_db
    main.user_store = UserStore(smoke_db)
    auth_mod.init_auth(main.user_store)

    if module_registry.is_enabled("bi"):
        from tars.api.bi import init_bi_api

        init_bi_api(smoke_db)

    if module_registry.is_enabled("insight") and module_registry.check_dependencies("insight")[0]:
        init_insight_api(smoke_db)
    else:
        pytest.skip("insight module not available for smoke tests")

    admin = None
    for u in main.user_store.get_all_users():
        if u.role == UserRole.ADMIN:
            admin = u
            break
    if not admin:
        name = f"smoke_admin_{uuid.uuid4().hex[:8]}"
        admin = main.user_store.create_user(
            username=name,
            email=f"{name}@smoke.test",
            role=UserRole.ADMIN,
        )

    case = seed(smoke_db, workflow_state="ready")

    headers = {
        "X-API-Key": admin.api_key,
        "X-Tenant-ID": USER_ID,
    }

    async def _smoke_insight_principal() -> Principal:
        return Principal(
            user_id=USER_ID,
            role="admin",
            role_template_id="admin",
            tenant_id=USER_ID,
            is_admin=True,
            api_key=admin.api_key,
        )

    main.app.dependency_overrides[insight_require] = _smoke_insight_principal

    with patch(
        "tars.insight.api.router.MetricQaEngine",
        side_effect=lambda db, **kwargs: _qa_engine_factory(db, **kwargs),
    ), patch.object(InsightJobRunner, "start_profile", _fake_forge_complete):
        with TestClient(main.app) as client:
            _skip_if_insight_unavailable(client)
            try:
                yield client, case, headers
            finally:
                main.app.dependency_overrides.pop(insight_require, None)


async def _fake_forge_complete(self, run_id, datasource_id, tenant_id="default"):
    """Complete forge immediately for smoke (no real profile pipeline)."""
    self.workflow.transition_on_profile_start(datasource_id, tenant_id)
    self.run_store.update_progress(
        run_id,
        tenant_id,
        {"phase": "done", "current": 1, "total": 1, "message": "smoke"},
        status="running",
    )
    self.run_store.complete(
        run_id, tenant_id, insight_snapshot={"tables": {}}, status="completed"
    )
    self.workflow.transition_on_profile_complete(datasource_id, tenant_id)


@pytest.mark.insight_smoke
@pytest.mark.parametrize("case", _SMOKE_CASES, ids=lambda c: c["id"])
def test_insight_smoke_suite_case(case, tars_smoke_stack):
    client, ctx, headers = tars_smoke_stack
    setup = case.get("setup") or {}
    if setup.get("workflow_state") == "needs_forge":
        from tars.insight.workflow_service import InsightWorkflowService

        InsightWorkflowService(ctx.db).set_datasource_state(
            ctx.datasource_id, USER_ID, "needs_forge"
        )
    run_smoke_steps(case, client, ctx, headers)


@pytest.mark.insight_smoke
def test_insight_smoke_health_chain(tars_smoke_stack):
    """Single linear smoke path mirroring Chat workflow strip → ask → feedback."""
    client, ctx, headers = tars_smoke_stack

    ver = client.get("/api/insight/version", headers=headers)
    assert ver.status_code == 200
    assert ver.json()["version"] == "INS-2.1.0"

    wf = client.get(
        f"/api/insight/datasources/{ctx.datasource_id}/workflow",
        headers=headers,
        params={"session_id": ctx.session_id},
    )
    assert wf.status_code == 200
    assert wf.json()["datasource_state"] == "ready"

    ask = client.post(
        f"/api/insight/datasources/{ctx.datasource_id}/ask",
        headers=headers,
        json={"question": "昨日 GMV", "session_id": ctx.session_id},
    )
    assert ask.status_code == 200
    body = ask.json()
    assert body["branch"] == "hit_approved"
    log_id = body["question_log_id"]

    fb = client.post(
        f"/api/insight/ask/{log_id}/feedback",
        headers=headers,
        json={"feedback": 1},
    )
    assert fb.status_code == 200

    brief = client.get(
        f"/api/insight/datasources/{ctx.datasource_id}/brief",
        headers=headers,
    )
    assert brief.status_code == 200
    assert "insight_snapshot" in brief.json()
