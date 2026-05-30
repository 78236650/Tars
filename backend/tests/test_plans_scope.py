"""v5.0 plan API uses datasource_scope_id (per-user tenant_id column)."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tars.api._auth import init_auth
from tars.api.plans import init_plans_api, router as plans_router
from tars.database import Database, UserStore
from tars.database.plan_store import PlanStore
from tars.gateway.permission import UserRole
from tars.middleware.user_context import UserContextMiddleware
from tars.orchestration.models import PlanStatus, TaskPlan, TaskStep


def _make_plan(store: PlanStore, *, plan_id: str, scope_user_id: str) -> None:
    plan = TaskPlan(
        goal="scoped plan",
        steps=[TaskStep(id=1, description="step", tool="calculator")],
    )
    plan.id = plan_id
    plan.session_id = "sess-1"
    plan.tenant_id = scope_user_id
    plan.status = PlanStatus.DRAFT
    store.create(plan)


@pytest.fixture
def plans_client(tmp_path):
    db = Database(db_path=str(tmp_path / "plans_scope.db"))
    store = UserStore(db)
    plan_store = PlanStore(db)
    plan_store.ensure_schema()
    suffix = uuid.uuid4().hex[:8]
    alice = store.create_user(
        username=f"alice_{suffix}",
        email=f"alice_{suffix}@t.local",
        role=UserRole.USER,
    )
    admin = store.create_user(
        username=f"admin_{suffix}",
        email=f"admin_{suffix}@t.local",
        role=UserRole.ADMIN,
    )
    from tars.database.auth_token_store import AuthTokenStore

    init_auth(store, AuthTokenStore(db))
    init_plans_api(db)

    _make_plan(plan_store, plan_id=f"plan-alice-{suffix}", scope_user_id=alice.id)

    app = FastAPI()
    app.state.user_store = store
    app.state.auth_token_store = AuthTokenStore(db)
    app.add_middleware(UserContextMiddleware)
    app.include_router(plans_router)
    client = TestClient(app)
    return client, alice, admin, suffix


def test_admin_lists_other_user_plans_with_user_id(plans_client):
    client, alice, admin, suffix = plans_client
    admin_headers = {"X-API-Key": admin.api_key}

    own = client.get("/api/plans/", headers=admin_headers).json()["plans"]
    assert all(p.get("tenant_id") != alice.id for p in own)

    other = client.get(
        f"/api/plans/?user_id={alice.id}",
        headers=admin_headers,
    ).json()["plans"]
    assert any(p["id"] == f"plan-alice-{suffix}" for p in other)


def test_non_admin_cannot_override_user_id(plans_client):
    client, alice, _admin, _suffix = plans_client
    headers = {"X-API-Key": alice.api_key}
    resp = client.get("/api/plans/?user_id=other-user", headers=headers)
    assert resp.status_code == 403
