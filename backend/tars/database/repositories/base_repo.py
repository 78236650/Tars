"""Repository Protocol 接口 — 所有 repo 的统一契约。

切 Postgres 时需重新实现各方法的 SQL。
迁移检查点：任何含 MATCH / FTS5 / sqlite_master / AUTOINCREMENT 的查询。
"""

from typing import Protocol


class Repository(Protocol):
    """Repository 接口协议。所有 domain repository 实现此接口。"""
    pass
