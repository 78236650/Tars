"""治理服务编排层 — 把 datasource_adapter + engine + repository 串起来。"""
from __future__ import annotations

from .datasource_adapter import fetch_rows
from .engine import run_checks
from .models import CheckRun
from .repository import GovernanceRepository


class GovernanceService:
    def __init__(self, db):
        self.db = db
        self.repo = GovernanceRepository(db)

    def run_validation(
        self,
        datasource_id: str,
        table_name: str,
        *,
        user_id: str = "default",
        tenant_id: str = "org_default",
    ) -> CheckRun:
        """拉数 → 查规则 → 跑引擎 → 落库 → 返回 CheckRun。"""
        # 1. 拉数
        result_set = fetch_rows(
            datasource_id, table=table_name,
            tenant_id=tenant_id,
        )

        # 2. 查该 datasource+table 下所有启用的规则
        rules = self.repo.list_rules(
            datasource_id=datasource_id,
            table_name=table_name,
            user_id=user_id,
        )
        if not rules:
            raise ValueError(f"数据源 {datasource_id} 表 {table_name} 下没有已启用的规则")

        # 3. 跑引擎（GE 先不接）
        check_run, result_rows = run_checks(
            result_set, rules,
            datasource_id=datasource_id,
            table_name=table_name,
            user_id=user_id,
            ge_engine=None,
        )

        # 4. 落库
        self.repo.save_check_run(check_run, result_rows)

        return check_run
