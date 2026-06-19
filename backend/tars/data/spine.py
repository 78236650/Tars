"""DataSpine — unified read-only datasource access for Layer2 modules."""
from __future__ import annotations

from ..database.bi_store import get_bi_store
from ..bi.sql_agent import SQLAgent
from .models import ResultSet


def fetch_rows(
    datasource_id: str,
    *,
    table: str | None = None,
    sql: str | None = None,
    max_rows: int = 10_000,
    tenant_id: str = "org_default",
) -> ResultSet:
    """Fetch rows from a datasource for governance, report, semantic, etc.

    ``table`` and ``sql`` are mutually exclusive.
    """
    if (table is None) == (sql is None):
        raise ValueError("fetch_rows: table 与 sql 必须二选一")

    store = get_bi_store()
    ds = store.get(datasource_id, tenant_id)
    if ds is None:
        raise ValueError(f"数据源不存在: {datasource_id}")

    query = sql if sql is not None else f"SELECT * FROM {table}"

    agent = SQLAgent(ds.connection_url)
    agent.security.max_rows = max_rows + 1
    result = agent.execute(query)

    if not result["success"]:
        raise RuntimeError(f"取数失败: {result['error']}")

    columns = result["columns"]
    data = result["data"]
    truncated = len(data) > max_rows
    if truncated:
        data = data[:max_rows]

    rows = [[row.get(c) for c in columns] for row in data]
    return ResultSet(rows=rows, column_names=columns, truncated=truncated)


def list_datasource_tables(
    datasource_id: str,
    *,
    tenant_id: str = "org_default",
) -> list[str]:
    """List table names for a datasource (schema introspection)."""
    store = get_bi_store()
    ds = store.get(datasource_id, tenant_id)
    if ds is None:
        raise ValueError(f"数据源不存在: {datasource_id}")

    agent = SQLAgent(ds.connection_url)
    schema = agent.get_schema()
    if not schema.get("success"):
        raise RuntimeError(schema.get("error", "schema 获取失败"))
    return [t["name"] for t in schema.get("tables", []) if t.get("name")]
