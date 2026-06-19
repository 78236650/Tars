"""Layer1 (Agent Core) optional module bootstrap."""
from __future__ import annotations

from .deps import BootstrapDeps


def mount_layer1_optional_routes(deps: BootstrapDeps) -> None:
    """Register Layer1 optional modules (meeting, orchestration, presales, skillhub)."""
    app = deps.app
    db = deps.db
    registry = deps.module_registry

    from tars.api.skillhub import router as skillhub_router
    from tars.api.meeting import router as meeting_router, init_meeting_api
    from tars.api.orchestration_routes import router as orchestration_router, init_orchestration_api
    from tars.api.presales import router as presales_router, init_presales_api

    if registry.is_enabled("skillhub"):
        app.include_router(skillhub_router)

    if registry.is_enabled("meeting"):
        app.include_router(meeting_router)
        init_meeting_api(
            db,
            deps.meeting_tool,
            deps.vector_store,
            deps.embedding_provider,
        )
    else:
        print("[Startup] 会议助手模块已禁用 (config/modules.yaml → meeting.enabled)")

    if registry.is_enabled("orchestration"):
        app.include_router(orchestration_router)
        init_orchestration_api(db)
        print("[Startup] 调度编排模块已启用 (plan_gate only)")
    else:
        print("[Startup] 调度编排模块已禁用 (config/modules.yaml → orchestration.enabled)")

    if registry.is_enabled("presales"):
        app.include_router(presales_router)
        init_presales_api(db)
        print("[Startup] 售前管理模块已启用")
    else:
        print("[Startup] 售前管理模块已禁用 (config/modules.yaml → presales.enabled)")

    # vessel_plan frozen — only mount if explicitly enabled (legacy)
    if registry.is_enabled("vessel_plan"):
        from tars.api.vessel_plan_routes import router as vessel_plan_router, init_vessel_plan_api
        app.include_router(vessel_plan_router)
        init_vessel_plan_api(db)
        print("[Startup] ⚠ vessel_plan 已废弃，建议禁用")
