"""Shared fixtures for InsightForge integration tests."""
from __future__ import annotations

from typing import AsyncIterator, Tuple
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tars.api._auth import Principal
from tars.database import Database
from tars.insight.metric_qa_engine import MetricQaEngine

from tests.insight.case_orders_shop import (
    TENANT,
    USER_ID,
    OrdersShopCase,
    mock_sql_executor,
    route_hit_gmv,
    seed,
)


@pytest.fixture
def orders_shop_case() -> OrdersShopCase:
    return seed()


@pytest.fixture
def orders_shop_needs_forge() -> OrdersShopCase:
    return seed(workflow_state="needs_forge")


def _qa_engine_factory(db: Database, route_fn=None) -> MetricQaEngine:
    return MetricQaEngine(
        db,
        route_fn=route_fn or route_hit_gmv,
        sql_executor=mock_sql_executor,
    )


@pytest.fixture
def insight_api_client(orders_shop_case: OrdersShopCase) -> Tuple[TestClient, OrdersShopCase]:
    """Minimal FastAPI app with insight router on the case in-memory DB."""
    from tars.insight.api.router import _require, init_insight_api, router

    init_insight_api(orders_shop_case.db)

    async def _principal() -> Principal:
        return Principal(
            user_id=USER_ID,
            role="admin",
            role_template_id="admin",
            tenant_id=TENANT,
            is_admin=True,
            api_key="case-test-key",
        )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_require] = _principal

    engine_patch = patch(
        "tars.insight.api.router.MetricQaEngine",
        side_effect=lambda db: _qa_engine_factory(db),
    )
    with engine_patch:
        with TestClient(app) as client:
            yield client, orders_shop_case
