"""fetch_rows 适配层测试 — 用临时 SQLite 文件做真实外部数据源。"""
import sqlite3
import pytest

from tars.governance.datasource_adapter import fetch_rows
from tars.database.bi_store import init_bi_store


@pytest.fixture
def sqlite_datasource(tmp_path, test_db):
    # 建一个真实 sqlite 文件作外部数据源
    dbfile = tmp_path / "ext.db"
    conn = sqlite3.connect(dbfile)
    conn.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    conn.executemany("INSERT INTO items VALUES (?, ?)", [(i, f"n{i}") for i in range(5)])
    conn.commit()
    conn.close()

    store = init_bi_store(test_db)
    ds = store.create(
        tenant_id="org_default",
        name="ext",
        db_type="sqlite",
        connection_url=f"sqlite:///{dbfile}",
    )
    return ds.id


def test_fetch_table_returns_rows(sqlite_datasource):
    rs = fetch_rows(sqlite_datasource, table="items", tenant_id="org_default")
    assert rs.column_names == ["id", "name"]
    assert len(rs.rows) == 5
    assert rs.truncated is False
    assert rs.rows[0] == [0, "n0"]


def test_truncated_flag(sqlite_datasource):
    rs = fetch_rows(sqlite_datasource, table="items", max_rows=3, tenant_id="org_default")
    assert len(rs.rows) == 3
    assert rs.truncated is True


def test_table_and_sql_mutually_exclusive(sqlite_datasource):
    with pytest.raises(ValueError):
        fetch_rows(sqlite_datasource, table="items", sql="SELECT 1", tenant_id="org_default")


def test_missing_datasource_raises(test_db):
    init_bi_store(test_db)
    with pytest.raises(ValueError):
        fetch_rows("nonexistent-id", table="items", tenant_id="org_default")
