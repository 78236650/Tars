"""Parametrized runner for tests/insight/workflow_suite.yaml (service + api layers)."""
from __future__ import annotations

import pytest

from tests.insight.case_orders_shop import seed
from tests.insight.conftest import _qa_engine_factory
from tests.insight.suite_runner import load_suite_cases, run_api_case, run_service_case

_SERVICE_CASES = load_suite_cases(layers=["service"])
_API_CASES = load_suite_cases(layers=["api"])


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("case", _SERVICE_CASES, ids=lambda c: c["id"])
async def test_workflow_suite_service(case):
    ctx = seed(
        workflow_state=(case.get("setup") or {}).get("workflow_state", "ready"),
        include_draft=(case.get("setup") or {}).get("include_draft", True),
    )
    await run_service_case(case, ctx)


@pytest.mark.integration
@pytest.mark.parametrize("case", _API_CASES, ids=lambda c: c["id"])
def test_workflow_suite_api(case, insight_api_client):
    client, ctx = insight_api_client
    setup = case.get("setup") or {}
    state = setup.get("workflow_state")
    if state:
        from tests.insight.case_orders_shop import TENANT
        from tars.insight.workflow_service import InsightWorkflowService

        InsightWorkflowService(ctx.db).set_datasource_state(
            ctx.datasource_id, TENANT, state
        )
    run_api_case(case, client, ctx)
