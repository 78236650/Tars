"""SQL 方言隔离层 — 未来切 Postgres 的迁移缝合点。

迁移检查点：任何含 MATCH / FTS5 / sqlite_master / AUTOINCREMENT 的查询。
"""


def placeholder(dialect: str) -> str:
    """Return the positional placeholder for the given dialect."""
    if dialect == "sqlite":
        return "?"
    if dialect == "postgres":
        return "%s"
    raise ValueError(f"unsupported dialect: {dialect}")


def insert_upsert(
    dialect: str,
    table: str,
    cols: list[str],
    conflict_cols: list[str] | None = None,
) -> str:
    """Build INSERT … ON CONFLICT upsert (Postgres) or INSERT OR IGNORE (SQLite)."""
    ph = placeholder(dialect)
    col_list = ", ".join(cols)
    val_list = ", ".join([ph] * len(cols))
    if dialect == "sqlite":
        return f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({val_list})"
    if dialect == "postgres":
        if not conflict_cols:
            return f"INSERT INTO {table} ({col_list}) VALUES ({val_list}) ON CONFLICT DO NOTHING"
        conflict = ", ".join(conflict_cols)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict_cols)
        if updates:
            return (
                f"INSERT INTO {table} ({col_list}) VALUES ({val_list}) "
                f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
            )
        return (
            f"INSERT INTO {table} ({col_list}) VALUES ({val_list}) "
            f"ON CONFLICT ({conflict}) DO NOTHING"
        )
    raise ValueError(f"unsupported dialect: {dialect}")


def fulltext_match_clause(
    dialect: str,
    column: str,
    keyword_param: str | None = None,
) -> str:
    """生成全文检索 WHERE 子句，根据方言不同返回对应语法。

    Args:
        dialect: "sqlite" | "postgres"
        column: 列名
        keyword_param: 参数占位符（默认 sqlite ``?`` / postgres ``%s``）
    """
    if keyword_param is None:
        keyword_param = placeholder(dialect)
    if dialect == "sqlite":
        return f"{column} MATCH ?"
    if dialect == "postgres":
        return f"to_tsvector('simple', {column}) @@ plainto_tsquery('simple', {keyword_param})"
    raise ValueError(f"unsupported dialect: {dialect}")
