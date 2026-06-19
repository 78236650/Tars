"""报表服务编排层 — 拉数 → 聚合 → 渲染。"""
from __future__ import annotations

from ..data.spine import fetch_rows
from .chartspec import ChartSpec
from .aggregate import aggregate
from .renderer import render, ChartData


class ReportService:
    def __init__(self, db):
        self.db = db

    def execute_chart(
        self,
        datasource_id: str,
        table_name: str,
        spec: ChartSpec,
        *,
        tenant_id: str = "org_default",
    ) -> ChartData:
        """从数据源拉数据 → 按 ChartSpec 聚合 → 渲染为 ChartData。"""
        # 1. 拉数据
        result_set = fetch_rows(
            datasource_id, table=table_name,
            tenant_id=tenant_id,
        )

        # 2. 聚合
        aggregated = aggregate(result_set.rows, result_set.column_names, spec)

        # 3. 渲染
        measures_count = len(spec.measures)
        return render(aggregated.columns, aggregated.rows, measures_count,
                     truncated=result_set.truncated)

    def validate_spec(
        self,
        datasource_id: str,
        table_name: str,
        spec: ChartSpec,
        *,
        tenant_id: str = "org_default",
    ) -> list[str]:
        """校验 ChartSpec 对目标数据源的字段是否合法。"""
        from .chartspec import validate_spec

        result_set = fetch_rows(
            datasource_id, table=table_name,
            max_rows=1, tenant_id=tenant_id,
        )
        return validate_spec(spec, result_set.column_names, {})
