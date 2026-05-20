"""InsightForge eval set runner (pytest -m insight_eval)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.config import InsightConfig, InsightFeatureFlags, InsightForgeSettings, InsightQaSettings
from tars.insight.metric_qa_engine import MetricQaEngine
from tars.insight.workflow_service import InsightWorkflowService

EVAL_PATH = Path(__file__).parent / "eval_set.yaml"


def _mock_sql(_url: str, sql: str):
    return {
        "success": True,
        "data": [{"value": 100}],
        "columns": ["value"],
        "row_count": 1,
        "error": None,
        "sql": sql,
    }


def _load_cases():
    raw = yaml.safe_load(EVAL_PATH.read_text(encoding="utf-8")) or {}
    return raw.get("cases") or []


def _insert_metric(db, ds_id, tenant, case):
    conn = db._get_conn()
    now = "2026-05-20T00:00:00"
    key = case.get("metric_key")
    if not key:
        return
    conn.execute(
        """
        INSERT INTO insight_metrics (
            id, datasource_id, tenant_id, metric_key, display_name, definition,
            sql_template, tables_json, status, source, confidence, created_at, updated_at,
            version, superseded_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, 'profile', 0.9, ?, ?, 1, NULL)
        """,
        (
            str(uuid.uuid4()),
            ds_id,
            tenant,
            key,
            key,
            case.get("definition") or key,
            case.get("sql_template") or "SELECT 1 AS value",
            case.get("status") or "approved",
            now,
            now,
        ),
    )
    conn.commit()


@pytest.mark.insight_eval
@pytest.mark.asyncio
@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c.get("id", "case"))
async def test_insight_eval_case(case):
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "eval-ds", "sqlite", "sqlite:///:memory:")
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "ready")
    _insert_metric(db, ds.id, "default", case)

    async def route(**kwargs):
        branch = case.get("branch", "miss")
        if branch == "hit_partial":
            return {
                "branch": "hit_partial",
                "confidence": 0.5,
                "open_questions": ["clarify"],
            }
        if branch == "miss":
            return {"branch": "miss", "confidence": 0.2}
        if branch == "adhoc":
            return {"branch": "adhoc", "confidence": 0.4}
        return {
            "branch": case.get("expect_branch", branch),
            "metric_key": case.get("metric_key"),
            "confidence": 0.9,
        }

    cfg = InsightConfig(
        qa=InsightQaSettings(allow_ad_hoc_sql=case.get("allow_ad_hoc_sql", True)),
        forge=InsightForgeSettings(),
        feature_flags=InsightFeatureFlags(),
    )
    engine = MetricQaEngine(db, config=cfg, route_fn=route, sql_executor=_mock_sql)
    ans = await engine.ask(
        ds.id,
        "default",
        case["question"],
        candidate_metric_keys=case.get("candidate_metric_keys"),
        is_second_partial_round=bool(case.get("candidate_metric_keys")),
    )
    assert ans.branch == case["expect_branch"]
    if case.get("expect_value") is not None:
        assert ans.value == case["expect_value"]
    if case.get("expect_error_code"):
        assert ans.error is not None
        assert ans.error.code == case["expect_error_code"]
        assert ans.value is None
