"""SQL 方言隔离层 — 未来切 Postgres 的迁移缝合点。

迁移检查点：任何含 MATCH / FTS5 / sqlite_master / AUTOINCREMENT 的查询。
"""


def fulltext_match_clause(dialect: str, column: str, keyword_param: str = ":kw") -> str:
    """生成全文检索 WHERE 子句，根据方言不同返回对应语法。

    Args:
        dialect: "sqlite" | "postgres"
        column: 列名
        keyword_param: 参数占位符（默认 :kw 用于 sqlite3 绑定）
    """
    if dialect == "sqlite":
        return f"{column} MATCH ?"
    if dialect == "postgres":
        return f"to_tsvector({column}) @@ plainto_tsquery({keyword_param})"
    raise ValueError(f"unsupported dialect: {dialect}")
