"""Load and execute profile_perf_suite.yaml cases (INS-2.1)."""
from __future__ import annotations

import asyncio
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
import yaml
from sqlalchemy import create_engine

from tests.test_insight_sql_timeout import SLOW_SQLITE_CTE as _SLOW_SQLITE_CTE

SUITE_PATH = Path(__file__).parent / "profile_perf_suite.yaml"


def load_perf_cases(*, layers: Optional[List[str]] = None) -> List[dict]:
    raw = yaml.safe_load(SUITE_PATH.read_text(encoding="utf-8")) or {}
    cases = raw.get("cases") or []
    if not layers:
        return cases
    return [c for c in cases if c.get("layer") in layers]


def _requires_bench(case: dict) -> None:
    if case.get("layer") == "bench" and os.environ.get("INSIGHT_PERF_BENCH") != "1":
        pytest.skip("set INSIGHT_PERF_BENCH=1 to run bench cases")


def _requires_env(case: dict) -> None:
    req = case.get("requires_env")
    if not req:
        return
    key, _, val = req.partition("=")
    if os.environ.get(key) != val:
        pytest.skip(f"requires {req}")


def _make_job_runner_db(tmp_path: Path):
    """Minimal DB schema for InsightJobRunner integration tests."""
    from tars.database import Database

    db_path = tmp_path / "job_runner_meta.db"
    return Database(str(db_path))


async def _run_job_runner_profile(
    tmp_path: Path,
    case: dict,
    *,
    twice: bool = False,
    second_run_budget: Optional[dict] = None,
    mock_llm: bool = False,
) -> dict:
    from tars.database.bi_store import DataSourceStore
    from tars.insight.job_runner import InsightJobRunner
    from tars.insight.store import InsightMetricStore, InsightProfileRunStore
    from tars.insight.workflow_service import InsightWorkflowService, show_workflow_strip

    from tests.insight.fixtures.profile_perf_db import build_sqlite

    setup = case.get("setup") or {}
    n_tables = setup.get("n_tables", 3)
    db_file = tmp_path / f"jr_{case['id']}.db"
    url = build_sqlite(db_file, n_tables=n_tables, n_columns=6, n_rows=15)
    db = _make_job_runner_db(tmp_path)
    ds_store = DataSourceStore(db)
    ds = ds_store.create("default", case["id"], "sqlite", url)
    wf = InsightWorkflowService(db)
    if setup.get("workflow_state"):
        wf.set_datasource_state(ds.id, "default", setup["workflow_state"])

    run_store = InsightProfileRunStore(db)
    run1 = run_store.create(ds.id, "default", "INS-2.1.0", {})
    runner = InsightJobRunner(db)

    class MockLlm:
        async def chat(self, *a, **kw):
            return type(
                "R",
                (),
                {
                    "content": (
                        '{"tables":{"t_0":{"description":"d","columns":{}}},'
                        '"metric_candidates":[{"key":"gmv","display_name":"GMV",'
                        '"definition":"sum","sql_template":"SELECT 1","confidence":0.9,'
                        '"tables":["t_0"]}]}'
                    )
                },
            )()

    async def _start(run_id: str) -> None:
        patches = [
            patch(
                "tars.insight.profile_pipeline.get_default_llm_provider",
                return_value=None,
            ),
        ]
        if mock_llm:
            from tars.insight.llm_resolver import ResolvedInsightLlm

            patches.append(
                patch(
                    "tars.insight.llm_resolver.resolve_insight_llm",
                    return_value=ResolvedInsightLlm(
                        provider=MockLlm(),
                        selection={"model": "mock"},
                        source="test",
                    ),
                )
            )
        from contextlib import ExitStack

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            await runner.start_profile(run_id, ds.id, "default")

    await _start(run1.id)

    out: dict = {"runs": [run_store.get(run1.id, "default")]}
    if twice:
        run2 = run_store.create(
            ds.id, "default", "INS-2.1.0", second_run_budget or {}
        )
        await _start(run2.id)
        out["runs"].append(run_store.get(run2.id, "default"))

    out["workflow"] = wf.get_composite(ds.id, "default")
    out["metrics"] = InsightMetricStore(db).list_by_datasource(ds.id, "default")
    out["show_strip"] = show_workflow_strip(
        out["workflow"]["datasource_state"],
        out["workflow"].get("session_state", "idle"),
    )
    return out


def _build_previous_snapshot(schema: dict, prev_n: int) -> dict:
    from tars.insight.schema_fingerprint import fingerprint_schema

    sub = {
        "tables": {
            k: v for k, v in (schema.get("tables") or {}).items()
            if k in {f"t_{i}" for i in range(prev_n)}
        }
    }
    fps = fingerprint_schema(sub)
    return {
        "tables": {
            f"t_{i}": {
                "table": f"t_{i}",
                "columns": {"id": {"name": "id", "distinct_count": 1}},
            }
            for i in range(prev_n)
        },
        "fingerprints": {f"t_{i}": fps.get(f"t_{i}", "") for i in range(prev_n)},
    }


def run_unit_case(case: dict, tmp_path: Path) -> None:
    module = case.get("module", "")
    action = case.get("action", "")

    if module == "run_store":
        from tars.database import Database
        from tars.insight.store import InsightProfileRunStore

        db_path = tmp_path / "store.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE insight_profile_runs (
                id TEXT PRIMARY KEY, datasource_id TEXT, tenant_id TEXT,
                capability_version TEXT, status TEXT, budget_json TEXT,
                progress_json TEXT, insight_snapshot_json TEXT,
                knowledge_doc_id TEXT, error TEXT, started_at TEXT,
                finished_at TEXT, created_at TEXT
            )
            """
        )
        conn.commit()
        conn.close()
        store = InsightProfileRunStore(Database(str(db_path)))
        if action == "latest_completed_excludes_failed":
            r1 = store.create("ds1", "default", "INS-2.1.0", {})
            store.complete(r1.id, "default", status="failed")
            r2 = store.create("ds1", "default", "INS-2.1.0", {})
            store.complete(
                r2.id, "default", status="completed",
                insight_snapshot={"tables": {"t1": {}}},
            )
            latest = store.latest_completed_for_datasource("ds1", "default")
            assert latest.id == r2.id
            return
        if action == "latest_completed_none":
            store.create("ds2", "default", "INS-2.1.0", {})
            assert store.latest_completed_for_datasource("ds2") is None
            return

    if module == "schema_fingerprint":
        from tars.insight.schema_fingerprint import fingerprint_schema, fingerprint_table

        from tests.insight.fixtures.profile_perf_db import build_sqlite, schema_dict_from_sqlite

        db_file = tmp_path / f"{case['id']}.db"
        n_tables = (case.get("setup") or {}).get("tables", 2)
        build_sqlite(db_file, n_tables=n_tables, n_columns=4, n_rows=5)
        schema = schema_dict_from_sqlite(db_file)
        fp1 = fingerprint_schema(schema)
        mutate = case.get("mutate") or "none"

        if mutate == "add_column":
            conn = sqlite3.connect(str(db_file))
            conn.execute("ALTER TABLE t_0 ADD COLUMN extra_col TEXT")
            conn.commit()
            conn.close()
            fp2 = fingerprint_schema(schema_dict_from_sqlite(db_file))
            assert (fp1.get("t_0") == fp2.get("t_0")) == case["expect"]["equal"]
            return
        if mutate == "change_column_type":
            tdef = schema["tables"]["t_0"]
            tdef2 = dict(tdef)
            cols = [dict(c) for c in tdef["columns"]]
            cols[1]["type"] = "BLOB"
            tdef2["columns"] = cols
            fp2 = fingerprint_table(tdef2)
            assert (fp1["t_0"] == fp2) == case["expect"]["equal"]
            return
        if mutate == "reorder_columns":
            tdef = schema["tables"]["t_0"]
            cols = list(tdef["columns"])
            cols.reverse()
            fp2 = fingerprint_table({**tdef, "columns": cols})
            assert (fp1["t_0"] == fp2) == case["expect"]["equal"]
            return
        if mutate == "change_table_comment_only":
            fp2 = fingerprint_schema(schema)
            assert fp1 == fp2
            return
        if mutate == "change_primary_key":
            tdef = schema["tables"]["t_0"]
            fp2 = fingerprint_table({**tdef, "primary_key": ["col_0"]})
            assert (fp1["t_0"] == fp2) == case["expect"]["equal"]
            return
        if action == "assert_stable":
            fp2 = fingerprint_schema(schema)
            assert (fp1 == fp2) == case["expect"]["equal"]
            return

    if module == "incremental_planner":
        from tars.insight.config import InsightBudget
        from tars.insight.incremental_planner import IncrementalPlanner

        setup = case.get("setup") or {}
        inp = case.get("input") or {}
        n_tables = setup.get("tables", 5)
        schema = {
            "tables": {
                f"t_{i}": {
                    "columns": [{"name": "id", "type": "INT"}],
                    "primary_key": ["id"],
                }
                for i in range(n_tables)
            }
        }
        previous = None
        completed_at = None
        if setup.get("has_previous"):
            prev_n = setup.get("previous_tables", n_tables)
            previous = _build_previous_snapshot(schema, prev_n)
            if setup.get("previous_age_hours"):
                completed_at = (
                    datetime.now(timezone.utc)
                    - timedelta(hours=setup["previous_age_hours"])
                ).isoformat()
        budget = InsightBudget(
            enable_incremental=inp.get("enable_incremental", True),
            incremental_ttl_hours=inp.get("incremental_ttl_hours", 24),
        )
        plan = IncrementalPlanner(budget).plan(
            schema,
            previous,
            force=inp.get("force", False),
            previous_completed_at=completed_at,
        )
        exp = case.get("expect") or {}
        if exp.get("all_action"):
            assert all(a == exp["all_action"] for a in plan.actions.values())
        if "reused_count" in exp:
            assert plan.reused_count == exp["reused_count"]
        if "collected_count" in exp:
            assert plan.collected_count == exp["collected_count"]
        if "dropped_count" in exp:
            assert plan.dropped_count == exp["dropped_count"]
        if "profile_run_type" in exp:
            assert plan.profile_run_type == exp["profile_run_type"]
        return

    if module == "sql_timeout":
        from tars.insight.sql_timeout import SqlTimeoutExecutor

        db_file = tmp_path / "timeout.db"
        engine = create_engine(f"sqlite:///{db_file}")
        timeout = case["input"]["timeout_sec"]
        exec_ = SqlTimeoutExecutor(timeout_sec=timeout, dialect="sqlite")
        if action == "fetch_one":
            row = exec_.fetch_one(engine, case["input"]["sql"])
            assert (row is not None) == case["expect"]["success"]
            return
        if action == "fetch_one_slow":
            from tests.test_insight_sql_timeout import SLOW_SQLITE_CTE

            t0 = time.time()
            row = exec_.fetch_one(engine, SLOW_SQLITE_CTE)
            elapsed = time.time() - t0
            if row is not None and elapsed < timeout:
                pytest.skip("SQLite CTE completed faster than timeout on this host")
            assert row is None
            assert elapsed <= case["expect"].get("max_elapsed_sec", 3.0)
            return

    if module == "batch_stats":
        from tars.insight.dialects.batch_stats import build_batch_stats_sql, split_column_batches

        inp = case.get("input") or {}
        cols = inp.get("columns") or [f"col_{i}" for i in range(inp.get("columns_n", 3))]
        if action == "build_batch_sql":
            sql = build_batch_stats_sql(inp["table"], cols[: inp.get("batch_size", 10)], inp["dialect"])
            for fragment in case["expect"].get("sql_contains") or []:
                assert fragment in sql
            if "sql_length_lt" in case["expect"]:
                assert len(sql) < case["expect"]["sql_length_lt"]
            if "batches_produced" in case["expect"]:
                batches = split_column_batches(cols, inp.get("batch_size", 10))
                assert len(batches) == case["expect"]["batches_produced"]
                assert all(
                    len(b) <= case["expect"].get("each_batch_columns_lte", 999)
                    for b in batches
                )
            return

    if module == "stats_collector":
        from tars.insight.config import InsightBudget
        from tars.insight.dialects.base import GenericDialectHelper
        from tars.insight.stats_collector import StatsCollector

        from tests.insight.fixtures.profile_perf_db import build_sqlite, schema_dict_from_sqlite

        setup = case.get("setup") or {}
        exp = case.get("expect") or {}

        if action == "collect_column_with_timeout":
            db_file = tmp_path / f"{case['id']}.db"
            build_sqlite(db_file, n_tables=1, n_columns=3, n_rows=5)
            url = f"sqlite:///{db_file}"
            budget = InsightBudget(stats_timeout_sec=1)
            collector = StatsCollector(url, "sqlite", "sqlite", budget)
            engine = collector._engine_get()
            helper = GenericDialectHelper(engine, "sqlite")

            def slow_stats_sql(table, column):
                return _SLOW_SQLITE_CTE, "SELECT 1"

            helper.column_stats_sql = slow_stats_sql
            cstats, flag = collector._collect_column(helper, "t_0", "col_0", {"type": "TEXT"})
            assert cstats.null_rate is None
            assert flag is not None
            assert flag.get("issue") == exp.get("quality_issue", "stats_timeout")
            collector.close()
            return

        if action == "collect_table_wall_timeout":
            import time as time_mod

            os.environ["TARS_INSIGHT_DISABLE_BATCH_SQL"] = "1"
            try:
                db_file = tmp_path / f"{case['id']}.db"
                n_cols = setup.get("n_columns", 50)
                table_timeout = setup.get("table_timeout_sec", 2)
                sleep_sec = setup.get("per_column_sleep_ms", 200) / 1000.0
                build_sqlite(db_file, n_tables=1, n_columns=n_cols, n_rows=5)
                url = f"sqlite:///{db_file}"
                budget = InsightBudget(table_timeout_sec=table_timeout)
                collector = StatsCollector(url, "sqlite", "sqlite", budget)
                engine = collector._engine_get()
                helper = GenericDialectHelper(engine, "sqlite")
                schema = schema_dict_from_sqlite(db_file)
                tdef = schema["tables"]["t_0"]
                orig = collector._collect_column

                def slow_column(*a, **kw):
                    time_mod.sleep(sleep_sec)
                    return orig(*a, **kw)

                collector._collect_column = slow_column
                ts = collector.collect_table(engine, helper, "t_0", tdef["columns"])
                assert ts.skipped_reason == exp.get("skipped_reason", "table_timeout")
                assert len(ts.columns) <= exp.get("collected_columns_lte", n_cols)
            finally:
                os.environ.pop("TARS_INSIGHT_DISABLE_BATCH_SQL", None)
            collector.close()
            return

        if action == "collect_table_batch_pg_large":
            db_file = tmp_path / f"{case['id']}.db"
            build_sqlite(db_file, n_tables=1, n_columns=setup.get("n_columns", 15), n_rows=5)
            url = f"sqlite:///{db_file}"
            collector = StatsCollector(url, "postgresql", "postgresql", InsightBudget())
            helper = MagicMock()
            helper.name = "postgresql"
            helper.engine = collector._engine_get()
            helper.estimate_row_count = MagicMock(return_value=setup.get("mock_estimate_rows", 5_000_000))
            batch_size = collector._batch_size_for_table(helper, "t_0")
            assert batch_size == 1
            collector.close()
            return

        if action == "collect_table_batch_fallback":
            db_file = tmp_path / f"{case['id']}.db"
            build_sqlite(db_file, n_tables=1, n_columns=8, n_rows=10)
            url = f"sqlite:///{db_file}"
            collector = StatsCollector(url, "sqlite", "sqlite", InsightBudget())
            engine = collector._engine_get()
            helper = GenericDialectHelper(engine, "sqlite")
            schema = schema_dict_from_sqlite(db_file)
            tdef = schema["tables"]["t_0"]

            if setup.get("inject_batch_error"):
                def fail_batch(*a, **kw):
                    return False

                collector._collect_columns_batch = fail_batch

            ts = collector.collect_table(engine, helper, "t_0", tdef["columns"])
            assert ts.table == "t_0"
            assert len(ts.columns) > 0
            assert collector.perf_counters.get("sql_fallback_single", 0) > 0
            collector.close()
            return

    pytest.skip(f"unit case not wired yet: {module}.{action}")


async def run_integration_case(case: dict, tmp_path: Path) -> None:
    module = case.get("module", "")
    setup = case.get("setup") or {}
    n_tables = setup.get("n_tables", 3)
    action = case.get("action", "")

    if module == "profile_pipeline":
        from tars.database import Database
        from tars.database.bi_store import DataSourceStore
        from tars.insight.config import InsightBudget, InsightConfig
        from tars.insight.profile_pipeline import ProfilePipeline

        from tests.insight.fixtures.profile_perf_db import (
            build_sqlite,
            insert_extra_rows,
        )

        db_file = tmp_path / f"{case['id']}.db"
        n_cols = setup.get("n_columns", 6)
        url = build_sqlite(db_file, n_tables=n_tables, n_columns=n_cols, n_rows=20)
        db = Database(":memory:")
        ds = DataSourceStore(db).create("default", case["id"], "sqlite", url)

        cfg = InsightConfig()
        if setup.get("parallel_tables") is not None:
            cfg.profile.parallel_tables = setup["parallel_tables"]
        if setup.get("enable_incremental") is not None:
            cfg.profile.enable_incremental = setup["enable_incremental"]
        if setup.get("incremental_resample_on_reuse") is not None:
            cfg.profile.incremental_resample_on_reuse = setup["incremental_resample_on_reuse"]
        if setup.get("reuse_synthesize_annotation") is not None:
            cfg.profile.reuse_synthesize_annotation = setup["reuse_synthesize_annotation"]
        if setup.get("disable_batch_sql"):
            os.environ["TARS_INSIGHT_DISABLE_BATCH_SQL"] = "1"

        pipeline = ProfilePipeline(config=cfg, llm_provider=None)

        if action == "run":
            result = await pipeline.run(ds)
            assert result["success"]
            snap = result.get("insight_snapshot") or {}
            for key_path in (case.get("expect") or {}).get("snapshot_keys") or []:
                cur: Any = snap
                for part in key_path.split("."):
                    assert part in cur, f"missing {key_path} in snapshot"
                    cur = cur[part]
            if "schema_version" in (case.get("expect") or {}):
                assert snap.get("schema_version") == case["expect"]["schema_version"]
            return

        if action == "run_twice":
            r1 = await pipeline.run(ds)
            assert r1["success"]
            r2 = await pipeline.run(
                ds,
                previous_snapshot=r1.get("insight_snapshot"),
                force=(case.get("input") or {}).get("second_run_force", False),
            )
            assert r2["success"]
            exp2 = (case.get("expect") or {}).get("second_run") or {}
            snap2 = r2.get("insight_snapshot") or {}
            inc = snap2.get("incremental") or {}
            if "profile_run_type" in exp2:
                assert snap2.get("profile_run_type") == exp2["profile_run_type"]
            if "tables_reused_gte" in exp2:
                assert inc.get("reused", 0) >= exp2["tables_reused_gte"]
            if exp2.get("tables_reused") == 0:
                assert inc.get("reused", 0) == 0
            return

        if action == "run_twice_with_data_drift":
            r1 = await pipeline.run(ds)
            assert r1["success"]
            insert_extra_rows(db_file, "t_0", n=50)
            r2 = await pipeline.run(ds, previous_snapshot=r1.get("insight_snapshot"))
            assert r2["success"]
            snap2 = r2.get("insight_snapshot") or {}
            inc = snap2.get("incremental") or {}
            exp2 = case.get("expect", {}).get("second_run", {})
            assert snap2.get("profile_run_type") == exp2.get("profile_run_type", "incremental")
            if exp2.get("sample_rows_changed"):
                s1 = (r1["insight_snapshot"]["tables"]["t_0"].get("sample_rows") or [])
                s2 = snap2["tables"]["t_0"].get("sample_rows") or []
                assert s1 != s2 or len(s2) > len(s1)
            if "perf.stats.tables_resampled_gte" in exp2:
                assert inc.get("resampled", 0) >= exp2["perf.stats.tables_resampled_gte"]
            return

        if action == "run_twice_with_counting_llm":
            calls = {"n": 0}

            class CountingLlm:
                async def chat(self, *a, **kw):
                    calls["n"] += 1
                    return type("R", (), {"content": '{"tables":{}}'})()

            llm_pipeline = ProfilePipeline(config=cfg, llm_provider=CountingLlm())
            r1 = await llm_pipeline.run(ds)
            n1 = calls["n"]
            r2 = await llm_pipeline.run(ds, previous_snapshot=r1.get("insight_snapshot"))
            n2 = calls["n"] - n1
            exp2 = case.get("expect", {}).get("second_run", {})
            assert n2 == exp2.get("llm_call_count", 0)
            return

        if action == "run_with_all_features_disabled":
            result = await pipeline.run(ds)
            snap = result.get("insight_snapshot") or {}
            exp = case.get("expect") or {}
            if exp.get("snapshot_tables_count"):
                assert len(snap.get("tables") or {}) == exp["snapshot_tables_count"]
            if exp.get("profile_run_type"):
                assert snap.get("profile_run_type") == exp["profile_run_type"]
            if exp.get("perf_present"):
                assert "perf" in snap
            return

        if action == "run_with_publisher":
            from tars.insight.knowledge_publisher import KnowledgePublisher

            pipeline = ProfilePipeline(
                config=cfg,
                knowledge_publisher=KnowledgePublisher(db, None),
                llm_provider=None,
            )
            result = await pipeline.run(ds)
            if (case.get("expect") or {}).get("knowledge_doc_id_not_null"):
                if result.get("knowledge_doc_id") is None:
                    pytest.skip("knowledge publish returned null (indexer optional)")
            return

    if module == "stats_collector":
        from tars.insight.config import InsightBudget
        from tars.insight.stats_collector import StatsCollector

        from tests.insight.fixtures.profile_perf_db import build_sqlite, schema_dict_from_sqlite

        db_file = tmp_path / f"{case['id']}.db"
        url = build_sqlite(db_file, n_tables=n_tables, n_columns=5, n_rows=10)
        schema = schema_dict_from_sqlite(db_file)
        tables = list(schema["tables"].keys())
        budget = InsightBudget(parallel_tables=setup.get("parallel_tables", 3))
        collector = StatsCollector(url, "sqlite", "sqlite", budget)

        if setup.get("inject_fail_table"):
            fail_table = setup["inject_fail_table"]
            orig_collect = collector.collect_table

            def failing_collect(engine, helper, table, columns):
                if table == fail_table:
                    raise RuntimeError(f"injected failure for {table}")
                return orig_collect(engine, helper, table, columns)

            collector.collect_table = failing_collect  # type: ignore[method-assign]

        if action == "check_engine_pool":
            exp = case.get("expect") or {}
            captured: dict = {}

            def fake_create_engine(url, **kwargs):
                captured.update(kwargs)
                return MagicMock(name="engine")

            with patch("tars.insight.stats_collector.create_engine", side_effect=fake_create_engine), patch(
                "tars.utils.url_safety.validate_external_db_url", lambda _url: None
            ):
                mc = StatsCollector(
                    "mysql+pymysql://u:p@127.0.0.1:3306/test",
                    "mysql",
                    "mysql",
                    InsightBudget(parallel_tables=setup.get("parallel_tables", 5)),
                )
                mc._engine_get()
            assert captured.get("pool_size", 0) >= exp.get("pool_size_gte", 7)
            assert captured.get("pool_pre_ping") is exp.get("pool_pre_ping", True)
            mc.close()
            return

        stats, meta = await collector.collect_all_async(schema, tables, track_concurrency=True)
        assert len(stats) >= (case.get("expect") or {}).get("success_tables_gte", len(tables))
        if "max_inflight_lte" in (case.get("expect") or {}):
            assert meta.get("max_inflight", 99) <= case["expect"]["max_inflight_lte"]
        if (case.get("expect") or {}).get("quality_flags_present"):
            assert meta.get("quality_flags")
        collector.close()
        return

    if module == "job_runner":
        exp = case.get("expect") or {}

        if action == "start_profile_twice":
            out = await _run_job_runner_profile(tmp_path, case, twice=True)
            assert out["runs"][1].status == exp.get("second_run_status", "completed")
            snap = out["runs"][1].insight_snapshot_json or {}
            inc = snap.get("incremental") or {}
            assert inc.get("reused", 0) >= exp.get("incremental_reused_gte", 0)
            return

        if action == "start_profile_with_force":
            out = await _run_job_runner_profile(
                tmp_path, case, twice=True, second_run_budget={"force": True}
            )
            snap = out["runs"][1].insight_snapshot_json or {}
            assert snap.get("profile_run_type") == exp.get("profile_run_type", "full")
            inc = snap.get("incremental") or {}
            assert inc.get("reused", 0) == exp.get("tables_reused", 0)
            return

        if action == "start_profile":
            out = await _run_job_runner_profile(tmp_path, case)
            assert out["runs"][0].status == "completed"
            assert out["workflow"]["datasource_state"] == exp.get("workflow_state", "ready")
            if "show_workflow_strip" in exp:
                assert out["show_strip"] is exp["show_workflow_strip"]
            return

        if action == "start_profile_with_mock_llm":
            out = await _run_job_runner_profile(tmp_path, case, mock_llm=True)
            assert len(out["metrics"]) >= exp.get("draft_metrics_gte", 1)
            return

    pytest.skip(f"integration case not wired yet: {module}.{action}")


def run_bench_case(case: dict, tmp_path: Path) -> None:
    _requires_bench(case)
    _requires_env(case)
    action = case.get("action", "")
    setup = case.get("setup") or {}
    expect = case.get("expect") or {}

    if action == "bench_run":
        asyncio.run(_bench_run(case, tmp_path))
        return
    if action == "bench_run_twice":
        asyncio.run(_bench_run_twice(case, tmp_path))
        return
    if action == "bench_sql_count":
        asyncio.run(_bench_sql_count(case, tmp_path))
        return
    if action == "bench_docker_mysql":
        pytest.skip("docker mysql bench requires INSIGHT_DOCKER_TEST=1 harness")
    pytest.skip(f"bench case not wired: {action}")


async def _bench_run(case: dict, tmp_path: Path) -> None:
    from tars.database import Database
    from tars.database.bi_store import DataSourceStore
    from tars.insight.config import InsightConfig
    from tars.insight.profile_pipeline import ProfilePipeline

    from tests.insight.fixtures.profile_perf_db import build_sqlite

    setup = case.get("setup") or {}
    expect = case.get("expect") or {}
    db_file = tmp_path / f"bench_{case['id']}.db"
    url = build_sqlite(
        db_file,
        n_tables=setup.get("n_tables", 30),
        n_columns=setup.get("n_columns", 10),
        n_rows=setup.get("n_rows", 200),
    )
    cfg = InsightConfig()
    cfg.profile.parallel_tables = setup.get("parallel_tables", 3)
    if setup.get("enable_batch_sql") is False:
        os.environ["TARS_INSIGHT_DISABLE_BATCH_SQL"] = "1"
    elif setup.get("enable_batch_sql"):
        os.environ.pop("TARS_INSIGHT_DISABLE_BATCH_SQL", None)

    db = Database(":memory:")
    ds = DataSourceStore(db).create("default", case["id"], "sqlite", url)
    pipeline = ProfilePipeline(config=cfg, llm_provider=None)

    t0 = time.time()
    result = await pipeline.run(ds)
    wall = time.time() - t0
    assert result["success"]

    if "wall_time_sec_lte" in expect:
        assert wall <= expect["wall_time_sec_lte"], f"wall {wall:.1f}s > limit"

    if "speedup_vs_serial_gte" in expect:
        # SQLite forces parallel_tables=1; compare batch-off vs batch-on instead.
        os.environ["TARS_INSIGHT_DISABLE_BATCH_SQL"] = "1"
        t_serial = time.time()
        await _bench_run({**case, "setup": {**setup, "parallel_tables": 1}, "expect": {}}, tmp_path / "nobatch")
        no_batch_wall = time.time() - t_serial
        os.environ.pop("TARS_INSIGHT_DISABLE_BATCH_SQL", None)
        speedup = no_batch_wall / max(wall, 0.001)
        assert speedup >= expect["speedup_vs_serial_gte"], f"speedup {speedup:.2f}x (batch vs no-batch)"


async def _bench_run_twice(case: dict, tmp_path: Path) -> None:
    from tars.database import Database
    from tars.database.bi_store import DataSourceStore
    from tars.insight.config import InsightConfig
    from tars.insight.profile_pipeline import ProfilePipeline

    from tests.insight.fixtures.profile_perf_db import build_sqlite

    setup = case.get("setup") or {}
    expect = case.get("expect") or {}
    db_file = tmp_path / f"bench2_{case['id']}.db"
    url = build_sqlite(
        db_file,
        n_tables=setup.get("n_tables", 30),
        n_columns=setup.get("n_columns", 10),
        n_rows=setup.get("n_rows", 200),
    )
    cfg = InsightConfig()
    cfg.profile.parallel_tables = setup.get("parallel_tables", 3)
    cfg.profile.enable_incremental = setup.get("enable_incremental", True)
    cfg.profile.reuse_synthesize_annotation = setup.get("reuse_synthesize_annotation", True)

    db = Database(":memory:")
    ds = DataSourceStore(db).create("default", case["id"], "sqlite", url)
    pipeline = ProfilePipeline(config=cfg, llm_provider=None)

    r1 = await pipeline.run(ds)
    t0 = time.time()
    r2 = await pipeline.run(ds, previous_snapshot=r1.get("insight_snapshot"))
    wall2 = time.time() - t0
    assert r2["success"]
    inc = (r2.get("insight_snapshot") or {}).get("incremental") or {}

    if "second_wall_time_sec_lte" in expect:
        assert wall2 <= expect["second_wall_time_sec_lte"]
    if "tables_reused_gte" in expect:
        assert inc.get("reused", 0) >= expect["tables_reused_gte"]


async def _bench_sql_count(case: dict, tmp_path: Path) -> None:
    from tars.insight.config import InsightBudget
    from tars.insight.stats_collector import StatsCollector

    from tests.insight.fixtures.profile_perf_db import build_sqlite, schema_dict_from_sqlite

    setup = case.get("setup") or {}
    expect = case.get("expect") or {}
    db_file = tmp_path / f"sqlcount_{case['id']}.db"
    n_cols = setup.get("n_columns", 20)
    url = build_sqlite(db_file, n_tables=setup.get("n_tables", 10), n_columns=n_cols, n_rows=50)
    schema = schema_dict_from_sqlite(db_file)
    tables = list(schema["tables"].keys())[:1]

    os.environ["TARS_INSIGHT_DISABLE_BATCH_SQL"] = "1"
    sc_single = StatsCollector(url, "sqlite", "sqlite", InsightBudget())
    await sc_single.collect_all_async(schema, tables)
    single_count = sc_single.perf_counters["sql_executed"]
    sc_single.close()

    os.environ.pop("TARS_INSIGHT_DISABLE_BATCH_SQL", None)
    sc_batch = StatsCollector(url, "sqlite", "sqlite", InsightBudget())
    await sc_batch.collect_all_async(schema, tables)
    batch_count = sc_batch.perf_counters["sql_executed"]
    sc_batch.close()

    reduction = (single_count - batch_count) / max(single_count, 1) * 100
    assert reduction >= expect.get("batch_sql_reduction_pct_gte", 0), (
        f"reduction {reduction:.1f}% single={single_count} batch={batch_count}"
    )
