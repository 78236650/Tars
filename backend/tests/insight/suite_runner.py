"""Load and execute InsightForge workflow_suite.yaml cases."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from tars.insight.adoption_service import AdoptionService
from tars.insight.job_runner import InsightJobRunner
from tars.insight.metric_qa_engine import InsightQaError, MetricQaEngine
from tars.insight.question_log_store import InsightQuestionLogStore
from tars.insight.store import InsightMetricStore, InsightProfileRunStore
from tars.insight.workflow_events import aiter_sse, publish
from tars.insight.workflow_service import InsightWorkflowService

from tests.insight.case_orders_shop import (
    TENANT,
    USER_ID,
    OrdersShopCase,
    mock_sql_executor,
    route_adhoc,
    route_hit_gmv,
    route_hit_partial,
    seed,
)

SUITE_PATH = Path(__file__).parent / "workflow_suite.yaml"


async def route_hit_order_count(**_kwargs: Any) -> dict:
    return {
        "branch": "hit_approved",
        "metric_key": "order_count",
        "confidence": 0.9,
        "reasoning": "case: order_count",
    }


async def route_miss(**_kwargs: Any) -> dict:
    return {"branch": "miss", "confidence": 0.2, "reasoning": "case: miss"}


ROUTE_PROFILES: Dict[str, Callable[..., Any]] = {
    "hit_gmv": route_hit_gmv,
    "hit_partial": route_hit_partial,
    "hit_order_count": route_hit_order_count,
    "adhoc": route_adhoc,
    "miss": route_miss,
}


def load_suite_cases(*, layers: Optional[List[str]] = None) -> List[dict]:
    raw = yaml.safe_load(SUITE_PATH.read_text(encoding="utf-8")) or {}
    cases = raw.get("cases") or []
    if not layers:
        return cases
    return [c for c in cases if c.get("layer") in layers]


def _setup_from_case(case: dict) -> OrdersShopCase:
    setup = case.get("setup") or {}
    return seed(
        workflow_state=setup.get("workflow_state", "ready"),
        include_draft=setup.get("include_draft", True),
    )


def _resolve_route(case: dict):
    profile = case.get("route_profile", "hit_gmv")
    fn = ROUTE_PROFILES.get(profile)
    if fn is None:
        raise ValueError(f"unknown route_profile: {profile}")
    return fn


async def run_service_case(case: dict, ctx: Optional[OrdersShopCase] = None) -> None:
    ctx = ctx or _setup_from_case(case)
    wf = InsightWorkflowService(ctx.db)
    action = case.get("action")

    if action == "ask":
        if case.get("expect_workflow"):
            composite = wf.get_composite(
                ctx.datasource_id, TENANT, ctx.session_id
            )
            for key, val in case["expect_workflow"].items():
                assert composite[key] == val, f"{key}: {composite[key]} != {val}"

        engine = MetricQaEngine(
            ctx.db,
            route_fn=_resolve_route(case),
            sql_executor=mock_sql_executor,
        )
        if case.get("expect_error"):
            try:
                await engine.ask(
                    ctx.datasource_id,
                    TENANT,
                    case["question"],
                    user_id=USER_ID,
                )
            except InsightQaError as e:
                assert e.code == case["expect_error"], e.code
            else:
                raise AssertionError(f"expected InsightQaError {case['expect_error']}")
            return

        ans = await engine.ask(
            ctx.datasource_id,
            TENANT,
            case["question"],
            user_id=USER_ID,
        )
        _assert_ask_expect(ans, case.get("expect") or {})
        return

    if action == "profile_complete":
        run_store = InsightProfileRunStore(ctx.db)
        run = run_store.create(ctx.datasource_id, TENANT, "INS-2.0.0", {})
        run_store.complete(run.id, TENANT, insight_snapshot={"tables": {}})
        wf.transition_on_profile_complete(ctx.datasource_id, TENANT)
        composite = wf.get_composite(ctx.datasource_id, TENANT, ctx.session_id)
        exp = case.get("expect_workflow") or {}
        for key, val in exp.items():
            assert composite[key] == val
        return

    if action == "check_session_unbound":
        session = ctx.db.create_session(tenant_id=TENANT)
        composite = wf.get_composite(ctx.datasource_id, TENANT, session.id)
        exp = case.get("expect_workflow") or {}
        for key, val in exp.items():
            assert composite[key] == val
        return

    if action == "pending_question_lifecycle":
        text = case.get("pending_text", "pending")
        wf.set_pending_question(
            ctx.datasource_id, TENANT, text, session_id=ctx.session_id
        )
        composite = wf.get_composite(ctx.datasource_id, TENANT)
        assert composite["pending_question"]["text"] == text
        consumed = wf.transition_on_profile_complete(ctx.datasource_id, TENANT)
        if case.get("expect_pending_consumed"):
            assert consumed is not None
            assert consumed["text"] == text
        after = wf.get_composite(ctx.datasource_id, TENANT)
        assert after.get("pending_question") is None
        return

    if action == "auto_ask_pending":
        text = case.get("pending_text", "昨日 GMV")
        wf.set_pending_question(ctx.datasource_id, TENANT, text, session_id=ctx.session_id)
        run_store = InsightProfileRunStore(ctx.db)
        run = run_store.create(ctx.datasource_id, TENANT, "INS-2.0.0", {})
        run_store.complete(run.id, TENANT, insight_snapshot={})
        mock_engine = MagicMock()
        mock_engine.ask = AsyncMock(return_value=MagicMock(branch="hit_approved"))
        runner = InsightJobRunner(ctx.db)
        with patch("tars.insight.metric_qa_engine.MetricQaEngine", return_value=mock_engine):
            pending = wf.transition_on_profile_complete(ctx.datasource_id, TENANT)
            assert pending is not None
            await runner._auto_ask_pending(ctx.datasource_id, TENANT, pending)
        if case.get("expect_auto_ask"):
            mock_engine.ask.assert_awaited_once()
        return

    if action == "adopt_draft":
        key = case.get("metric_key", "gmv_draft")
        mid = ctx.metric_ids[key]
        result = AdoptionService(ctx.db).adopt(mid, TENANT, USER_ID)
        assert result["status"] == (case.get("expect") or {}).get("status", "approved")
        return

    if action == "feedback_downgrade":
        key = case.get("metric_key", "gmv")
        mid = ctx.metric_ids[key]
        qlog = InsightQuestionLogStore(ctx.db)
        adoption = AdoptionService(ctx.db)
        n = case.get("negative_count", 3)
        for _ in range(n):
            lid = qlog.insert_log(
                datasource_id=ctx.datasource_id,
                tenant_id=TENANT,
                question="负反馈",
                sql="SELECT 1",
                branch="hit_approved",
                outcome="success",
                caliber_tier="official",
                user_id=USER_ID,
                metric_key=key,
            )
            qlog.update_feedback(lid, TENANT, -1)
            adoption.process_feedback(lid, TENANT, -1, USER_ID)
        metric = InsightMetricStore(ctx.db).get_by_id(mid, TENANT)
        exp_status = (case.get("expect") or {}).get("metric_status", "deprecated")
        assert metric.status == exp_status
        return

    if action == "sse_smoke":
        run_id = f"suite-sse-{case['id']}"
        publish(run_id, "progress", {"message": "suite"})
        publish(run_id, "completed", {"run_id": run_id})
        chunks: list[str] = []

        async def _collect():
            agen = aiter_sse(run_id, 0, heartbeat_sec=999, poll_interval_sec=0.05)
            async for chunk in agen:
                chunks.append(chunk)
                if "completed" in chunk:
                    break
            await agen.aclose()

        await asyncio.wait_for(_collect(), timeout=3.0)
        joined = "".join(chunks)
        for ev in case.get("expect_sse_events") or []:
            assert f"event: {ev}" in joined
        return

    raise ValueError(f"unsupported service action: {action}")


def run_api_case(
    case: dict,
    client: Any,
    ctx: OrdersShopCase,
) -> None:
    action = case.get("action")
    wf = InsightWorkflowService(ctx.db)

    if action == "http_workflow":
        res = client.get(
            f"/api/insight/datasources/{ctx.datasource_id}/workflow",
            params={"session_id": ctx.session_id},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        for key, val in (case.get("expect") or {}).items():
            assert body[key] == val, f"{key}: {body.get(key)}"
        return

    if action == "http_ask_feedback":
        ask_res = client.post(
            f"/api/insight/datasources/{ctx.datasource_id}/ask",
            json={
                "question": case.get("question", "昨日 GMV"),
                "session_id": ctx.session_id,
            },
        )
        assert ask_res.status_code == 200, ask_res.text
        body = ask_res.json()
        for key, val in (case.get("expect") or {}).items():
            assert body.get(key) == val
        log_id = body["question_log_id"]
        fb = client.post(
            f"/api/insight/ask/{log_id}/feedback",
            json={"feedback": 1},
        )
        assert fb.status_code == 200, fb.text
        return

    if action == "http_adopt":
        key = case.get("metric_key", "gmv_draft")
        mid = ctx.metric_ids[key]
        res = client.post(
            f"/api/insight/metrics/{mid}/adopt",
            json={"definition": "suite adopt"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == (case.get("expect") or {}).get("status")
        return

    if action == "http_forge_pending":
        wf.set_datasource_state(ctx.datasource_id, TENANT, "needs_forge")
        with patch.object(InsightJobRunner, "start_profile", new_callable=AsyncMock):
            res = client.post(
                f"/api/insight/datasources/{ctx.datasource_id}/forge",
                json={
                    "pending_question": case.get("pending_text", "pending"),
                    "session_id": ctx.session_id,
                },
            )
        assert res.status_code == 200, res.text
        composite = wf.get_composite(ctx.datasource_id, TENANT)
        prefix = case.get("expect_pending_prefix", "")
        assert composite["pending_question"]["text"].startswith(prefix)
        return

    raise ValueError(f"unsupported api action: {action}")


def run_smoke_steps(
    case: dict,
    client: Any,
    ctx: OrdersShopCase,
    headers: Dict[str, str],
) -> None:
    """Execute declarative HTTP steps against main TARS app."""
    saved: Dict[str, Any] = {}
    template_vars = {
        "datasource_id": ctx.datasource_id,
        "session_id": ctx.session_id,
        "tenant_id": ctx.tenant_id,
        "metric_id_gmv_draft": ctx.metric_ids.get("gmv_draft", ""),
    }

    def _template_map() -> Dict[str, Any]:
        flat = dict(template_vars)
        for key, val in saved.items():
            flat[key] = val
            if isinstance(val, dict):
                for sub_key, sub_val in val.items():
                    flat[f"{key}.{sub_key}"] = sub_val
        return flat

    def _fmt(value: Any) -> Any:
        if isinstance(value, str):
            return value.format(**_template_map())
        if isinstance(value, dict):
            return {k: _fmt(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_fmt(v) for v in value]
        return value

    for step in case.get("steps") or []:
        method = step["method"].upper()
        path = _fmt(step["path"])
        kwargs: Dict[str, Any] = {"headers": headers}
        if step.get("query"):
            kwargs["params"] = _fmt(step["query"])
        if step.get("json") is not None:
            kwargs["json"] = _fmt(step["json"])

        res = client.request(method, path, **kwargs)
        expect_status = step.get("expect_status", 200)
        assert res.status_code == expect_status, res.text

        if res.status_code == 200 and res.headers.get("content-type", "").startswith(
            "application/json"
        ):
            body = res.json()
            if step.get("expect_json"):
                for key, val in step["expect_json"].items():
                    assert body.get(key) == val, f"{key}={body.get(key)} expected {val}"
            if step.get("expect_json_keys"):
                for key in step["expect_json_keys"]:
                    assert key in body, f"missing key {key} in {list(body.keys())}"
            if step.get("expect_json_nonempty"):
                for key in step["expect_json_nonempty"]:
                    assert body.get(key), f"{key} should be non-empty"
            if step.get("save_as"):
                saved[step["save_as"]] = body
                for field in (
                    "question_log_id",
                    "run_id",
                    "id",
                    "metric_key",
                    "branch",
                ):
                    if field in body:
                        saved[field] = body[field]


def _assert_ask_expect(ans: Any, expect: dict) -> None:
    for key, val in expect.items():
        if key == "has_candidates":
            assert bool(ans.candidates) == val
            continue
        if key == "sql_contains":
            assert val.upper() in (ans.sql or "").upper()
            continue
        if key == "error_code":
            assert ans.error is not None
            assert ans.error.code == val
            continue
        assert getattr(ans, key, None) == val, f"{key}: {getattr(ans, key)} != {val}"

