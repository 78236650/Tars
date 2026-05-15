"""BI Analytics Skill - Plugin 入口

注册 BI 相关工具到 TARS 全局 tool_registry
"""
from typing import Any, Dict, List, Optional

from tars.tools.base import BaseTool, ToolResult
from tars.database.bi_store import DataSourceStore
from tars.database.base import Database
from tars.bi.schema_explorer import SchemaExplorer
from tars.bi.sql_agent import SQLAgent
from tars.bi.chart_generator import ChartGenerator


# 全局 DataSourceStore 实例（在 main.py 启动时注入）
_bi_store: Optional[DataSourceStore] = None


def _get_store() -> DataSourceStore:
    global _bi_store
    if _bi_store is None:
        db = Database()
        _bi_store = DataSourceStore(db)
    return _bi_store


class BIListDataSourcesTool(BaseTool):
    """列出当前租户下已配置的所有数据源"""

    name: str = "bi_list_datasources"
    description: str = "列出所有已配置的数据库数据源，获取数据源 ID、名称、类型和 Schema 信息。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "tenant_id": {
                "type": "string",
                "description": "租户 ID，默认 'default'",
            },
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        tenant_id = kwargs.get("tenant_id", "default")
        store = _get_store()
        datasources = store.list_by_tenant(tenant_id)

        if not datasources:
            return ToolResult(
                success=True,
                output="当前没有配置任何数据源。",
                metadata={"datasources": []},
            )

        lines = [f"共 {len(datasources)} 个数据源："]
        ds_list = []
        for ds in datasources:
            table_names = list(ds.schema_snapshot.get("tables", {}).keys())
            lines.append(f"- {ds.name} (ID: {ds.id}, 类型: {ds.db_type}, 表: {', '.join(table_names[:5]) or '无'})")
            ds_list.append({
                "id": ds.id,
                "name": ds.name,
                "db_type": ds.db_type,
                "tables": table_names,
                "annotations": ds.schema_annotations,
            })

        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"datasources": ds_list},
        )


class BIQueryTool(BaseTool):
    """在指定数据源上执行只读 SQL 查询"""

    name: str = "bi_query"
    description: str = "在指定数据源上执行 SQL 查询（只读，仅支持 SELECT/WITH）。需要提供数据源 ID 和 SQL 语句。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "datasource_id": {
                "type": "string",
                "description": "数据源 ID",
            },
            "sql": {
                "type": "string",
                "description": "SQL 查询语句（只读）",
            },
            "tenant_id": {
                "type": "string",
                "description": "租户 ID，默认 'default'",
            },
        },
        "required": ["datasource_id", "sql"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        ds_id = kwargs.get("datasource_id", "").strip()
        sql = kwargs.get("sql", "").strip()
        tenant_id = kwargs.get("tenant_id", "default")

        if not ds_id or not sql:
            return ToolResult(success=False, output="", error="请提供 datasource_id 和 sql")

        store = _get_store()
        ds = store.get(ds_id, tenant_id)
        if not ds:
            return ToolResult(success=False, output="", error=f"数据源 '{ds_id}' 不存在")

        agent = SQLAgent(ds.connection_url)
        try:
            result = agent.execute(sql)
            if result["success"]:
                row_count = result["row_count"]
                columns = result["columns"]
                preview = result["data"][:5]
                lines = [
                    f"查询成功，返回 {row_count} 行数据，列: {', '.join(columns)}",
                    "",
                    "前 5 行预览：",
                ]
                for row in preview:
                    lines.append(str(row))
                return ToolResult(
                    success=True,
                    output="\n".join(lines),
                    metadata=result,
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result["error"],
                    metadata=result,
                )
        finally:
            agent.close()


class BIGenerateChartTool(BaseTool):
    """执行 SQL 并生成 ECharts 图表配置"""

    name: str = "bi_generate_chart"
    description: str = "执行 SQL 查询并自动生成 ECharts 图表。支持 line、bar、pie、scatter、table 类型。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "datasource_id": {
                "type": "string",
                "description": "数据源 ID",
            },
            "sql": {
                "type": "string",
                "description": "SQL 查询语句",
            },
            "chart_type": {
                "type": "string",
                "description": "图表类型: line/bar/pie/scatter/table，不传则自动推断",
            },
            "user_question": {
                "type": "string",
                "description": "用户原始问题，用于生成图表标题",
            },
            "tenant_id": {
                "type": "string",
                "description": "租户 ID，默认 'default'",
            },
        },
        "required": ["datasource_id", "sql"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        ds_id = kwargs.get("datasource_id", "").strip()
        sql = kwargs.get("sql", "").strip()
        chart_type = kwargs.get("chart_type")
        user_question = kwargs.get("user_question", "")
        tenant_id = kwargs.get("tenant_id", "default")

        if not ds_id or not sql:
            return ToolResult(success=False, output="", error="请提供 datasource_id 和 sql")

        store = _get_store()
        ds = store.get(ds_id, tenant_id)
        if not ds:
            return ToolResult(success=False, output="", error=f"数据源 '{ds_id}' 不存在")

        agent = SQLAgent(ds.connection_url)
        try:
            result = agent.execute(sql)
            if not result["success"]:
                return ToolResult(success=False, output="", error=result["error"], metadata=result)

            generator = ChartGenerator()
            chart = generator.generate(
                data=result["data"],
                columns=result["columns"],
                user_question=user_question,
                chart_type=chart_type,
            )

            summary = chart.get("data_summary", "")
            chart_type_str = chart.get("chart_type", "table")

            output_lines = [
                f"图表类型: {chart_type_str}",
                f"数据摘要: {summary}",
                f"共 {len(result['data'])} 行数据",
            ]

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                metadata={
                    "chart": chart,
                    "sql": result["sql"],
                    "raw_data": result["data"],
                    "columns": result["columns"],
                },
            )
        finally:
            agent.close()


class BISchemaExploreTool(BaseTool):
    """探索指定数据源的 Schema 信息"""

    name: str = "bi_schema_explore"
    description: str = "获取指定数据源的表结构、字段、外键关系等 Schema 信息。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "datasource_id": {
                "type": "string",
                "description": "数据源 ID",
            },
            "tenant_id": {
                "type": "string",
                "description": "租户 ID，默认 'default'",
            },
        },
        "required": ["datasource_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        ds_id = kwargs.get("datasource_id", "").strip()
        tenant_id = kwargs.get("tenant_id", "default")

        if not ds_id:
            return ToolResult(success=False, output="", error="请提供 datasource_id")

        store = _get_store()
        ds = store.get(ds_id, tenant_id)
        if not ds:
            return ToolResult(success=False, output="", error=f"数据源 '{ds_id}' 不存在")

        schema = ds.schema_snapshot
        tables = schema.get("tables", {})

        lines = [f"数据源 '{ds.name}' 共 {len(tables)} 张表：", ""]
        for table_name, table_info in tables.items():
            columns = table_info.get("columns", [])
            col_descs = [f"{c['name']}({c['type']})" for c in columns[:5]]
            if len(columns) > 5:
                col_descs.append("...")
            lines.append(f"表: {table_name}")
            lines.append(f"  字段: {', '.join(col_descs)}")
            pk = table_info.get("primary_key", [])
            if pk:
                lines.append(f"  主键: {', '.join(pk)}")
            fks = table_info.get("foreign_keys", [])
            if fks:
                for fk in fks:
                    lines.append(f"  外键: {fk['column']} -> {fk['referred_table']}.{fk['referred_column']}")
            lines.append("")

        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"schema": schema, "annotations": ds.schema_annotations},
        )
