"""Tests for adopt → knowledge metric card publish."""
from unittest.mock import MagicMock

import pytest

from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.adoption_service import AdoptionService
from tars.insight.config import InsightAdoptionSettings, InsightConfig
from tars.insight.knowledge_bridge import KnowledgeBridge
from tars.insight.store import InsightMetricStore
from tars.knowledge.sqlite_store import get_document_metadata


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def tenant_ds(db):
    bi = DataSourceStore(db)
    ds = bi.create("default", "shop", "sqlite", "sqlite:///:memory:")
    return ds


def test_adopt_publishes_metric_card_metadata(db, tenant_ds, monkeypatch):
    store = InsightMetricStore(db)
    metric = store.create_draft_from_log(
        datasource_id=tenant_ds.id,
        tenant_id="default",
        metric_key="gmv",
        display_name="GMV",
        definition="不含退款",
        sql_template="SELECT SUM(amount) FROM orders",
        source="profile",
    )

    published: dict = {}

    class FakePublisher:
        def publish(
            self,
            datasource_id,
            datasource_name,
            markdown,
            tenant_id="default",
            run_id=None,
            metric_ids=None,
        ):
            published["markdown"] = markdown
            published["metric_ids"] = metric_ids
            doc_id = "doc-metric-1"
            conn = db._get_conn()
            conn.execute(
                "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"insight_{datasource_id}", tenant_id, "test", "", "2026-05-24", "2026-05-24"),
            )
            conn.execute(
                "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, created_at, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, f"insight_{datasource_id}", "card.md", "", "md", "indexed", "2026-05-24", "{}"),
            )
            conn.commit()
            from tars.knowledge.sqlite_store import set_document_metadata

            if metric_ids:
                set_document_metadata(db, doc_id, {"metric_ids": metric_ids})
            return doc_id

    bridge = KnowledgeBridge(db=db, indexer=MagicMock())
    bridge._publisher = FakePublisher()

    cfg = InsightConfig()
    cfg.adoption = InsightAdoptionSettings(publish_to_knowledge=True, require_review=False)
    svc = AdoptionService(db, config=cfg, knowledge_bridge=bridge)

    result = svc.adopt(metric.id, "default", "user1", defer_publish=True)
    svc.publish_adopted_metric(metric, "default", "user1")
    assert result["status"] == "approved"
    assert "gmv" in published.get("markdown", "")
    assert metric.id in (published.get("metric_ids") or [])

    meta = get_document_metadata(db, "doc-metric-1")
    assert metric.id in meta.get("metric_ids", [])
