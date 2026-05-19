"""InsightForge Profile pipeline integration tests."""
import asyncio
import sqlite3

import pytest

from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.profile_pipeline import ProfilePipeline
from tars.insight.relation_inferencer import RelationInferencer
from tars.insight.role_classifier import RoleClassifier
from tars.insight.stats_collector import StatsCollector
from tars.insight.store import InsightMetricStore, InsightProfileRunStore


@pytest.fixture
def bi_sqlite_db(tmp_path):
    db_path = tmp_path / "insight_bi.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE bi_datasources (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            db_type TEXT NOT NULL,
            connection_url TEXT NOT NULL,
            readonly INTEGER DEFAULT 1,
            schema_snapshot TEXT DEFAULT '{}',
            schema_annotations TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE insight_profile_runs (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            capability_version TEXT NOT NULL,
            status TEXT NOT NULL,
            budget_json TEXT NOT NULL,
            progress_json TEXT NOT NULL DEFAULT '{}',
            insight_snapshot_json TEXT,
            knowledge_doc_id TEXT,
            error TEXT,
            started_at TEXT,
            finished_at TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE insight_metrics (
            id TEXT PRIMARY KEY,
            datasource_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            definition TEXT NOT NULL,
            sql_template TEXT DEFAULT '',
            tables_json TEXT DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'draft',
            source TEXT NOT NULL DEFAULT 'profile',
            confidence REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(datasource_id, tenant_id, metric_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE document_collections (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    db = Database(str(db_path))
    return db


@pytest.fixture
def sample_datasource(bi_sqlite_db):
  store = DataSourceStore(bi_sqlite_db)
  # in-memory analytics db
  analytics = sqlite3.connect(":memory:")
  analytics.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
  analytics.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)")
  analytics.execute("INSERT INTO users VALUES (1, 'alice'), (2, 'bob')")
  analytics.execute("INSERT INTO orders VALUES (1, 1, 100.0), (2, 1, 50.0), (3, 2, 200.0)")
  analytics.commit()
  analytics.close()

  ds = store.create(
      tenant_id="default",
      name="test-orders",
      db_type="sqlite",
      connection_url="sqlite:///:memory:",
  )
  # Re-open shared memory not possible across connections — use file sqlite
  return ds


@pytest.fixture
def file_datasource(bi_sqlite_db, tmp_path):
    analytics_path = tmp_path / "analytics.db"
    conn = sqlite3.connect(str(analytics_path))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)")
    conn.execute("INSERT INTO users VALUES (1, 'alice'), (2, 'bob')")
    conn.execute("INSERT INTO orders VALUES (1, 1, 100.0), (2, 1, 50.0), (3, 2, 200.0)")
    conn.commit()
    conn.close()

    store = DataSourceStore(bi_sqlite_db)
    return store.create(
        tenant_id="default",
        name="file-orders",
        db_type="sqlite",
        connection_url=f"sqlite:///{analytics_path}",
    )


def test_stats_collector_sqlite(file_datasource):
    from tars.insight.config import InsightBudget

    budget = InsightBudget(max_tables=10, max_columns_per_table=20, sample_rows_per_table=10)
    collector = StatsCollector(
        file_datasource.connection_url, "sqlite", "sqlite", budget
    )
    schema = collector.collect_schema()
    assert "users" in schema.get("tables", {})
    stats = collector.collect_all(schema)
    assert "orders" in stats
    assert "amount" in stats["orders"].columns
    collector.close()


def test_relation_inferencer():
    schema = {
        "tables": {
            "orders": {
                "columns": [{"name": "user_id"}],
                "foreign_keys": [
                    {"column": "user_id", "referred_table": "users", "referred_column": "id"}
                ],
            },
            "users": {"columns": [{"name": "id"}], "foreign_keys": []},
        }
    }
    edges = RelationInferencer().infer(schema, {}, ["orders", "users"])
    assert any(e.type == "fk_declared" for e in edges)


@pytest.mark.anyio
async def test_profile_pipeline_e2e(file_datasource, bi_sqlite_db):
    from tars.insight.knowledge_publisher import KnowledgePublisher

    ds_store = DataSourceStore(bi_sqlite_db)
    ds = ds_store.get(file_datasource.id, "default")
    pipeline = ProfilePipeline(knowledge_publisher=KnowledgePublisher(bi_sqlite_db, None))
    result = await pipeline.run(ds)
    assert result["success"] is True
    assert "users" in (result["schema_annotations"] or {})
    snapshot = result["insight_snapshot"]
    assert snapshot.get("profile_mode") == "full"
    assert "orders" in snapshot.get("tables", {})


@pytest.mark.anyio
async def test_job_runner_updates_datasource(file_datasource, bi_sqlite_db):
    from tars.insight.job_runner import InsightJobRunner

    ds_store = DataSourceStore(bi_sqlite_db)
    run_store = InsightProfileRunStore(bi_sqlite_db)
    run = run_store.create(file_datasource.id, "default", "INS-1.0.0", {})
    runner = InsightJobRunner(bi_sqlite_db)
    await runner.start_profile(run.id, file_datasource.id, "default")

    finished = run_store.get(run.id, "default")
    assert finished.status == "completed"
    ds = ds_store.get(file_datasource.id, "default")
    assert "insight" in (ds.schema_snapshot or {})
    assert "orders" in (ds.schema_annotations or {})

    metric_store = InsightMetricStore(bi_sqlite_db)
    # metrics may be empty without LLM
    assert metric_store.list_by_datasource(file_datasource.id, "default") is not None
