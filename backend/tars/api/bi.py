"""BI Analytics API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from ..database import Database
from ..database.bi_store import DataSource, DataSourceStore, init_bi_store
from ..bi.connection_config import (
    ConnectionConfig,
    config_from_payload,
    parse_connection_url,
    serialize_stored_config,
    to_public_dict,
)
from ..bi.schema_explorer import SchemaExplorer
from ..bi.sql_agent import SQLAgent
from ..bi.chart_generator import ChartGenerator
from ._auth import Principal, require_module
from .scope import datasource_scope_id

router = APIRouter(prefix="/api/datasources", tags=["BI Analytics"])

_require = require_module("bi")
router.dependencies = [Depends(_require)]

_db: Optional[Database] = None
_store: Optional[DataSourceStore] = None


def init_bi_api(db: Database) -> None:
    global _db, _store
    _db = db
    _store = init_bi_store(db)


# ========== Pydantic 模型 ==========

class ConnectionFields(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None


class CreateDataSourceRequest(BaseModel):
    name: str
    db_type: str = Field(
        ...,
        pattern="^(mysql|postgresql|oracle|sqlserver|clickhouse|sqlite|doris|jdbc)$",
    )
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    connection_url: Optional[str] = None


class UpdateDataSourceRequest(BaseModel):
    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    connection_url: Optional[str] = None


class TestConnectionConfigRequest(BaseModel):
    db_type: str = Field(
        ...,
        pattern="^(mysql|postgresql|oracle|sqlserver|clickhouse|sqlite|doris|jdbc)$",
    )
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    connection_url: Optional[str] = None


class UpdateAnnotationsRequest(BaseModel):
    annotations: Dict[str, Any]


class ExecuteSQLRequest(BaseModel):
    sql: str


class GenerateChartRequest(BaseModel):
    sql: str
    chart_type: Optional[str] = None
    user_question: str = ""


def _uses_structured_fields(**fields) -> bool:
    return any(v is not None and v != "" for v in fields.values())


def _resolve_connection(
    *,
    db_type: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    connection_url: Optional[str] = None,
    existing: Optional[DataSource] = None,
) -> tuple[ConnectionConfig, str, dict[str, Any]]:
    structured = _uses_structured_fields(
        host=host, port=port, username=username, password=password, database=database,
    )

    effective_password = password
    if structured and (effective_password is None or effective_password == "") and existing:
        effective_password = parse_connection_url(existing.connection_url, existing.db_type).password

    try:
        if structured:
            cfg, url = config_from_payload(
                db_type=db_type,
                host=host,
                port=port,
                username=username,
                password=effective_password,
                database=database,
            )
        elif connection_url:
            cfg, url = config_from_payload(db_type=db_type, connection_url=connection_url)
        elif existing:
            cfg = parse_connection_url(existing.connection_url, existing.db_type)
            url = existing.connection_url
        else:
            raise ValueError("请填写连接信息")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    stored_config = to_public_dict(cfg, mask_password=True)
    return cfg, url, stored_config


def _serialize_datasource(ds: DataSource) -> dict[str, Any]:
    connection = serialize_stored_config(ds.connection_config_json, ds.connection_url, ds.db_type)
    return {
        "id": ds.id,
        "name": ds.name,
        "db_type": ds.db_type,
        "readonly": ds.readonly,
        "connection": connection,
        "schema_snapshot": ds.schema_snapshot,
        "schema_annotations": ds.schema_annotations,
        "created_at": ds.created_at,
        "updated_at": ds.updated_at,
    }


def _test_url(connection_url: str) -> tuple[bool, str]:
    explorer = SchemaExplorer(connection_url)
    try:
        return explorer.test_connection()
    finally:
        explorer.close()


# ========== DataSource CRUD ==========

@router.get("/")
async def list_datasources(
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """获取当前用户数据源列表（管理员可传 ``user_id`` 查看他人）。"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")
    datasources = _store.list_by_tenant(datasource_scope_id(principal, user_id=user_id))
    return {"datasources": [_serialize_datasource(ds) for ds in datasources]}


@router.post("/test-config")
async def test_connection_config(
    request: TestConnectionConfigRequest,
    principal: Principal = Depends(_require),
):
    """测试连接配置（保存前）"""
    _ = principal
    _, url, _ = _resolve_connection(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database,
        connection_url=request.connection_url,
    )
    ok, msg = _test_url(url)
    return {"success": ok, "message": msg}


@router.post("/")
async def create_datasource(
    request: CreateDataSourceRequest,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """创建数据源 + 自动抓取 schema"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds_scope = datasource_scope_id(principal, user_id=user_id)
    _, connection_url, stored_config = _resolve_connection(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database,
        connection_url=request.connection_url,
    )

    ok, msg = _test_url(connection_url)
    if not ok:
        raise HTTPException(status_code=400, detail=f"连接测试失败: {msg}")

    explorer = SchemaExplorer(connection_url)
    try:
        schema = explorer.explore()
    except Exception:
        schema = {}
    finally:
        explorer.close()

    ds = _store.create(
        tenant_id=ds_scope,
        name=request.name,
        db_type=request.db_type,
        connection_url=connection_url,
        readonly=True,
        schema_snapshot=schema,
        connection_config_json=stored_config,
    )

    return {"success": True, "datasource": _serialize_datasource(ds)}


@router.get("/{ds_id}")
async def get_datasource(
    ds_id: str,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """获取数据源详情"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds = _store.get(ds_id, datasource_scope_id(principal, user_id=user_id))
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    return _serialize_datasource(ds)


@router.put("/{ds_id}")
async def update_datasource(
    ds_id: str,
    request: UpdateDataSourceRequest,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """更新数据源配置"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds_scope = datasource_scope_id(principal, user_id=user_id)
    ds = _store.get(ds_id, ds_scope)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    update_data: dict[str, Any] = {}
    if request.name is not None:
        update_data["name"] = request.name

    connection_touched = _uses_structured_fields(
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database,
    ) or request.connection_url is not None or request.db_type is not None

    if connection_touched:
        db_type = request.db_type or ds.db_type
        _, connection_url, stored_config = _resolve_connection(
            db_type=db_type,
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            database=request.database,
            connection_url=request.connection_url,
            existing=ds,
        )
        ok, msg = _test_url(connection_url)
        if not ok:
            raise HTTPException(status_code=400, detail=f"连接测试失败: {msg}")
        update_data["db_type"] = db_type
        update_data["connection_url"] = connection_url
        update_data["connection_config_json"] = stored_config

    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    updated = _store.update(ds_id, ds_scope, **update_data)
    return {"success": True, "datasource": _serialize_datasource(updated)}


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: str,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """删除数据源"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ok = _store.delete(ds_id, datasource_scope_id(principal, user_id=user_id))
    if not ok:
        raise HTTPException(status_code=404, detail="数据源不存在")

    return {"success": True, "message": "数据源已删除"}


@router.post("/{ds_id}/test")
async def test_datasource_connection(
    ds_id: str,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """测试数据源连接"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds = _store.get(ds_id, datasource_scope_id(principal, user_id=user_id))
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    ok, msg = _test_url(ds.connection_url)
    return {"success": ok, "message": msg}


@router.post("/{ds_id}/refresh-schema")
async def refresh_schema(
    ds_id: str,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """重新抓取 schema"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds_scope = datasource_scope_id(principal, user_id=user_id)
    ds = _store.get(ds_id, ds_scope)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    explorer = SchemaExplorer(ds.connection_url)
    try:
        schema = explorer.explore()
        updated = _store.update(ds_id, ds_scope, schema_snapshot=schema)
        return {
            "success": True,
            "schema_snapshot": updated.schema_snapshot,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema 抓取失败: {e}")
    finally:
        explorer.close()


@router.put("/{ds_id}/annotations")
async def update_annotations(
    ds_id: str,
    request: UpdateAnnotationsRequest,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """更新 schema 标注"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds_scope = datasource_scope_id(principal, user_id=user_id)
    ds = _store.get(ds_id, ds_scope)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    updated = _store.update(ds_id, ds_scope, schema_annotations=request.annotations)
    return {"success": True, "schema_annotations": updated.schema_annotations}


# ========== SQL 查询 ==========

@router.post("/{ds_id}/query")
async def execute_query(
    ds_id: str,
    request: ExecuteSQLRequest,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """执行 SQL 查询（只读）"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds_scope = datasource_scope_id(principal, user_id=user_id)
    ds = _store.get(ds_id, ds_scope)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    agent = SQLAgent(ds.connection_url)
    try:
        result = agent.execute(request.sql)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询执行失败: {e}")
    finally:
        agent.close()


# ========== 图表生成 ==========

@router.post("/{ds_id}/chart")
async def generate_chart(
    ds_id: str,
    request: GenerateChartRequest,
    user_id: Optional[str] = None,
    principal: Principal = Depends(_require),
):
    """执行 SQL 并生成图表"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds_scope = datasource_scope_id(principal, user_id=user_id)
    ds = _store.get(ds_id, ds_scope)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    agent = SQLAgent(ds.connection_url)
    try:
        result = agent.execute(request.sql)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        generator = ChartGenerator()
        chart = generator.generate(
            data=result["data"],
            columns=result["columns"],
            user_question=request.user_question,
            chart_type=request.chart_type,
        )
        return chart
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图表生成失败: {e}")
    finally:
        agent.close()
