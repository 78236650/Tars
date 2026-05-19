"""BI Analytics API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from ..database import Database
from ..database.bi_store import DataSourceStore
from ..bi.schema_explorer import SchemaExplorer
from ..bi.sql_agent import SQLAgent
from ..bi.chart_generator import ChartGenerator
from ._auth import Principal, require_module

router = APIRouter(prefix="/api/datasources", tags=["BI Analytics"])

_require = require_module("bi")
router.dependencies = [Depends(_require)]

_db: Optional[Database] = None
_store: Optional[DataSourceStore] = None


def init_bi_api(db: Database) -> None:
    global _db, _store
    _db = db
    _store = DataSourceStore(db)


# ========== Pydantic 模型 ==========

class CreateDataSourceRequest(BaseModel):
    name: str
    db_type: str = Field(
        ...,
        pattern="^(mysql|postgresql|oracle|sqlserver|clickhouse|sqlite|doris|jdbc)$",
    )
    connection_url: str


class UpdateDataSourceRequest(BaseModel):
    name: Optional[str] = None
    db_type: Optional[str] = None
    connection_url: Optional[str] = None


class UpdateAnnotationsRequest(BaseModel):
    annotations: Dict[str, Any]


class ExecuteSQLRequest(BaseModel):
    sql: str


class GenerateChartRequest(BaseModel):
    sql: str
    chart_type: Optional[str] = None
    user_question: str = ""


# ========== DataSource CRUD ==========

@router.get("/")
async def list_datasources(principal: Principal = Depends(_require)):
    """获取当前租户数据源列表"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")
    datasources = _store.list_by_tenant(principal.tenant_id)
    return {
        "datasources": [
            {
                "id": ds.id,
                "name": ds.name,
                "db_type": ds.db_type,
                "readonly": ds.readonly,
                "schema_snapshot": ds.schema_snapshot,
                "schema_annotations": ds.schema_annotations,
                "created_at": ds.created_at,
                "updated_at": ds.updated_at,
            }
            for ds in datasources
        ]
    }


@router.post("/")
async def create_datasource(
    request: CreateDataSourceRequest,
    principal: Principal = Depends(_require),
):
    """创建数据源 + 自动抓取 schema"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    tenant_id = principal.tenant_id

    # 先测试连接
    explorer = SchemaExplorer(request.connection_url)
    ok, msg = explorer.test_connection()
    if not ok:
        raise HTTPException(status_code=400, detail=f"连接测试失败: {msg}")

    # 抓取 schema
    try:
        schema = explorer.explore()
    except Exception as e:
        schema = {}
    finally:
        explorer.close()

    ds = _store.create(
        tenant_id=tenant_id,
        name=request.name,
        db_type=request.db_type,
        connection_url=request.connection_url,
        readonly=True,
        schema_snapshot=schema,
    )

    return {
        "success": True,
        "datasource": {
            "id": ds.id,
            "name": ds.name,
            "db_type": ds.db_type,
            "readonly": ds.readonly,
            "schema_snapshot": ds.schema_snapshot,
            "schema_annotations": ds.schema_annotations,
            "created_at": ds.created_at,
            "updated_at": ds.updated_at,
        }
    }


@router.get("/{ds_id}")
async def get_datasource(
    ds_id: str,
    principal: Principal = Depends(_require),
):
    """获取数据源详情"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds = _store.get(ds_id, principal.tenant_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    return {
        "id": ds.id,
        "name": ds.name,
        "db_type": ds.db_type,
        "readonly": ds.readonly,
        "schema_snapshot": ds.schema_snapshot,
        "schema_annotations": ds.schema_annotations,
        "created_at": ds.created_at,
        "updated_at": ds.updated_at,
    }


@router.put("/{ds_id}")
async def update_datasource(
    ds_id: str,
    request: UpdateDataSourceRequest,
    principal: Principal = Depends(_require),
):
    """更新数据源配置"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    tenant_id = principal.tenant_id
    ds = _store.get(ds_id, tenant_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.db_type is not None:
        update_data["db_type"] = request.db_type
    if request.connection_url is not None:
        update_data["connection_url"] = request.connection_url

    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    updated = _store.update(ds_id, tenant_id, **update_data)
    return {"success": True, "datasource": {
        "id": updated.id,
        "name": updated.name,
        "db_type": updated.db_type,
        "readonly": updated.readonly,
        "schema_snapshot": updated.schema_snapshot,
        "schema_annotations": updated.schema_annotations,
        "created_at": updated.created_at,
        "updated_at": updated.updated_at,
    }}


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: str,
    principal: Principal = Depends(_require),
):
    """删除数据源"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ok = _store.delete(ds_id, principal.tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="数据源不存在")

    return {"success": True, "message": "数据源已删除"}


@router.post("/{ds_id}/test")
async def test_datasource_connection(
    ds_id: str,
    principal: Principal = Depends(_require),
):
    """测试数据源连接"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    ds = _store.get(ds_id, principal.tenant_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    explorer = SchemaExplorer(ds.connection_url)
    try:
        ok, msg = explorer.test_connection()
        return {"success": ok, "message": msg}
    finally:
        explorer.close()


@router.post("/{ds_id}/refresh-schema")
async def refresh_schema(
    ds_id: str,
    principal: Principal = Depends(_require),
):
    """重新抓取 schema"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    tenant_id = principal.tenant_id
    ds = _store.get(ds_id, tenant_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    explorer = SchemaExplorer(ds.connection_url)
    try:
        schema = explorer.explore()
        updated = _store.update(ds_id, tenant_id, schema_snapshot=schema)
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
    principal: Principal = Depends(_require),
):
    """更新 schema 标注"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    tenant_id = principal.tenant_id
    ds = _store.get(ds_id, tenant_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    updated = _store.update(ds_id, tenant_id, schema_annotations=request.annotations)
    return {"success": True, "schema_annotations": updated.schema_annotations}


# ========== SQL 查询 ==========

@router.post("/{ds_id}/query")
async def execute_query(
    ds_id: str,
    request: ExecuteSQLRequest,
    principal: Principal = Depends(_require),
):
    """执行 SQL 查询（只读）"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    tenant_id = principal.tenant_id
    ds = _store.get(ds_id, tenant_id)
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
    principal: Principal = Depends(_require),
):
    """执行 SQL 并生成图表"""
    if _store is None:
        raise HTTPException(status_code=500, detail="BI API 未初始化")

    tenant_id = principal.tenant_id
    ds = _store.get(ds_id, tenant_id)
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
