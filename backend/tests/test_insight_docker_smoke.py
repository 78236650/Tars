"""Smoke tests against local Docker insightforge-db (optional).

Run:
  cd deploy/insightforge-db && ./scripts/up.sh
  cd backend && INSIGHT_DOCKER_TEST=1 pytest tests/test_insight_docker_smoke.py -v
"""
import os

import pytest

RUN_DOCKER = os.environ.get("INSIGHT_DOCKER_TEST") == "1"

MYSQL_URL = os.environ.get(
    "INSIGHT_MYSQL_URL",
    "mysql+pymysql://insight:insight_pass@127.0.0.1:3307/insight_demo",
)
PG_URL = os.environ.get(
    "INSIGHT_PG_URL",
    "postgresql+psycopg2://insight:insight_pass@127.0.0.1:5433/insight_demo",
)
DORIS_URL = os.environ.get(
    "INSIGHT_DORIS_URL",
    "mysql+pymysql://root@127.0.0.1:9030/insight_demo",
)


def _can_connect(url: str) -> bool:
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def _gmv(url: str) -> float:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        val = conn.execute(
            text("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'paid'")
        ).scalar()
    engine.dispose()
    return float(val)


@pytest.mark.skipif(not RUN_DOCKER, reason="set INSIGHT_DOCKER_TEST=1 to run")
def test_mysql_gmv():
    if not _can_connect(MYSQL_URL):
        pytest.skip("mysql not running on 3307")
    assert _gmv(MYSQL_URL) == 4197.0


@pytest.mark.skipif(not RUN_DOCKER, reason="set INSIGHT_DOCKER_TEST=1 to run")
def test_postgres_gmv():
    if not _can_connect(PG_URL):
        pytest.skip("postgres not running on 5433")
    assert _gmv(PG_URL) == 4197.0


@pytest.mark.skipif(not RUN_DOCKER, reason="set INSIGHT_DOCKER_TEST=1 to run")
def test_doris_gmv():
    if not _can_connect(DORIS_URL):
        pytest.skip("doris not running on 9030")
    assert _gmv(DORIS_URL) == 4197.0


@pytest.mark.skipif(not RUN_DOCKER, reason="set INSIGHT_DOCKER_TEST=1 to run")
@pytest.mark.asyncio
async def test_profile_mysql_pipeline():
    if not _can_connect(MYSQL_URL):
        pytest.skip("mysql not running")
    from tars.database import Database
    from tars.database.bi_store import DataSourceStore
    from tars.insight.profile_pipeline import ProfilePipeline

    db = Database()
    store = DataSourceStore(db)
    ds = store.create(
        tenant_id="default",
        name="docker-mysql-demo",
        db_type="mysql",
        connection_url=MYSQL_URL,
    )
    pipeline = ProfilePipeline()
    result = await pipeline.run(ds)
    assert result["success"] is True
    assert "orders" in (result.get("schema_annotations") or {})
