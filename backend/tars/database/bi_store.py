"""BI Analytics - DataSource Store"""
import json
import uuid
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from .base import Database, get_local_now

_bi_store_singleton: Optional["DataSourceStore"] = None


def init_bi_store(db: Database) -> "DataSourceStore":
    """Wire the shared DataSourceStore used by REST API and BI agent tools."""
    global _bi_store_singleton
    _bi_store_singleton = DataSourceStore(db)
    return _bi_store_singleton


def get_bi_store() -> "DataSourceStore":
    """Return the app-wide store, or lazily create one for legacy callers."""
    global _bi_store_singleton
    if _bi_store_singleton is None:
        _bi_store_singleton = DataSourceStore(Database())
    return _bi_store_singleton


@dataclass
class DataSource:
    id: str
    tenant_id: str
    name: str
    db_type: str
    connection_url: str
    readonly: bool = True
    schema_snapshot: Dict[str, Any] = field(default_factory=dict)
    schema_annotations: Dict[str, Any] = field(default_factory=dict)
    connection_config_json: str = "{}"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DataSourceStore:
    _SELECT_COLUMNS = (
        "id, tenant_id, name, db_type, connection_url, readonly, "
        "schema_snapshot, schema_annotations, created_at, updated_at, connection_config_json"
    )

    def __init__(self, db: Database):
        self.db = db

    def _now(self) -> str:
        return get_local_now().isoformat()

    def create(
        self,
        tenant_id: str,
        name: str,
        db_type: str,
        connection_url: str,
        readonly: bool = True,
        schema_snapshot: Optional[Dict[str, Any]] = None,
        schema_annotations: Optional[Dict[str, Any]] = None,
        connection_config_json: Optional[Dict[str, Any]] = None,
    ) -> DataSource:
        ds_id = str(uuid.uuid4())
        now = self._now()
        snapshot_json = json.dumps(schema_snapshot or {}, ensure_ascii=False)
        annotations_json = json.dumps(schema_annotations or {}, ensure_ascii=False)
        config_json = json.dumps(connection_config_json or {}, ensure_ascii=False)

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bi_datasources (
                id, tenant_id, name, db_type, connection_url, readonly,
                schema_snapshot, schema_annotations, created_at, updated_at, connection_config_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ds_id, tenant_id, name, db_type, connection_url, 1 if readonly else 0,
                snapshot_json, annotations_json, now, now, config_json,
            ),
        )
        conn.commit()

        return DataSource(
            id=ds_id,
            tenant_id=tenant_id,
            name=name,
            db_type=db_type,
            connection_url=connection_url,
            readonly=readonly,
            schema_snapshot=schema_snapshot or {},
            schema_annotations=schema_annotations or {},
            connection_config_json=config_json,
            created_at=now,
            updated_at=now,
        )

    def get(self, ds_id: str, tenant_id: str = "default") -> Optional[DataSource]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {self._SELECT_COLUMNS} FROM bi_datasources WHERE id = ? AND tenant_id = ?",
            (ds_id, tenant_id),
        )
        row = cursor.fetchone()
        return self._row_to_datasource(row) if row else None

    def list_by_tenant(self, tenant_id: str = "default") -> List[DataSource]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {self._SELECT_COLUMNS} FROM bi_datasources WHERE tenant_id = ? ORDER BY updated_at DESC",
            (tenant_id,),
        )
        return [self._row_to_datasource(row) for row in cursor.fetchall()]

    def update(self, ds_id: str, tenant_id: str = "default", **kwargs) -> Optional[DataSource]:
        allowed = {
            "name", "db_type", "connection_url", "readonly",
            "schema_snapshot", "schema_annotations", "connection_config_json",
        }
        updates = []
        params = []

        for key, value in kwargs.items():
            if key not in allowed:
                continue
            if key in ("schema_snapshot", "schema_annotations", "connection_config_json"):
                if isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False)
            elif key == "readonly":
                value = 1 if value else 0
            updates.append(f"{key} = ?")
            params.append(value)

        if not updates:
            return self.get(ds_id, tenant_id)

        updates.append("updated_at = ?")
        params.append(self._now())
        params.append(ds_id)
        params.append(tenant_id)

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE bi_datasources SET {', '.join(updates)} WHERE id = ? AND tenant_id = ?",
            params,
        )
        conn.commit()
        return self.get(ds_id, tenant_id)

    def delete(self, ds_id: str, tenant_id: str = "default") -> bool:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM bi_datasources WHERE id = ? AND tenant_id = ?",
            (ds_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_datasource(self, row) -> Optional[DataSource]:
        if not row:
            return None
        try:
            schema_snapshot = json.loads(row[6] or "{}")
        except (json.JSONDecodeError, TypeError):
            schema_snapshot = {}
        try:
            schema_annotations = json.loads(row[7] or "{}")
        except (json.JSONDecodeError, TypeError):
            schema_annotations = {}

        config_json = "{}"
        if len(row) > 10 and row[10]:
            config_json = row[10]

        return DataSource(
            id=row[0],
            tenant_id=row[1],
            name=row[2],
            db_type=row[3],
            connection_url=row[4],
            readonly=bool(row[5]),
            schema_snapshot=schema_snapshot,
            schema_annotations=schema_annotations,
            connection_config_json=config_json,
            created_at=row[8],
            updated_at=row[9],
        )
