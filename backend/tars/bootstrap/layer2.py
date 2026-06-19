"""Layer2 (Port Data Platform) bootstrap — routes and module init."""
from __future__ import annotations

from .deps import BootstrapDeps


def mount_layer2_routes(deps: BootstrapDeps) -> None:
    """Register Layer2 optional module routers and init APIs."""
    app = deps.app
    db = deps.db
    agent = deps.agent
    registry = deps.module_registry
    evolution = deps.evolution_manager

    from tars.api.bi import router as bi_router, init_bi_api
    from tars.insight.api import router as insight_router
    from tars.insight.api.router import init_insight_api

    if registry.is_enabled("bi"):
        app.include_router(bi_router)
        init_bi_api(db)
    else:
        print("[Startup] BI 分析台模块已禁用 (config/modules.yaml → bi.enabled)")

    if registry.is_enabled("insight"):
        ok, msg = registry.check_dependencies("insight")
        if ok:
            app.include_router(insight_router)
            init_insight_api(
                db,
                knowledge_indexer=None,
                feedback_collector=evolution.feedback_collector if evolution else None,
                llm_provider=agent.provider,
            )
            from tars.insight.version import INS_VERSION
            print(f"[Startup] InsightForge 鉴数已启用 ({INS_VERSION})")
        else:
            print(f"[Startup] InsightForge 未加载: {msg}")

    if registry.is_enabled("governance"):
        from tars.governance.api.router import router as governance_router, init_governance_api
        init_governance_api(db)
        app.include_router(governance_router)
        print("[Startup] 数据治理模块已启用")
    else:
        print("[Startup] 数据治理模块已禁用 (config/modules.yaml → governance.enabled)")

    if registry.is_enabled("report"):
        from tars.report.api.router import router as report_router, init_report_api
        init_report_api(db)
        app.include_router(report_router)
        print("[Startup] 数据报表模块已启用")
    else:
        print("[Startup] 数据报表模块已禁用 (config/modules.yaml → report.enabled)")

    if registry.is_enabled("semantic"):
        ok, msg = registry.check_dependencies("semantic")
        if ok:
            from tars.semantic.api.router import router as semantic_router, init_semantic_api
            init_semantic_api(db)
            app.include_router(semantic_router)
            print("[Startup] 语义层/术语库模块已启用")
        else:
            print(f"[Startup] 语义层模块未加载: {msg}")
