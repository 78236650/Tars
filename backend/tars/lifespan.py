"""TARS Application Lifespan — startup/shutdown 钩子（从 main.py 拆分）。"""

import os


async def run_startup(db, tool_registry, skill_registry, memory_manager,
                       cron_runtime, init_scheduler, ensure_default_admin):
    """执行所有启动初始化（被 main.py 的 @app.on_event("startup") 调用）。"""
    await init_scheduler()
    await cron_runtime.load_from_db()
    ensure_default_admin()

    # 遗忘清理
    stats = memory_manager.cleanup()
    if stats["decayed"] or stats["deleted"]:
        print(f"[Startup] 记忆遗忘: importance衰减={stats['decayed']} 删除={stats['deleted']}")

    # 清理过期 Working Context
    try:
        db.cleanup_working_contexts()
    except Exception:
        pass

    # 崩溃恢复 — 扫描未完成任务，置为 paused
    try:
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, title FROM tasks WHERE status IN ('running','pending')")
        stale = cur.fetchall()
        if stale:
            cur.execute("UPDATE tasks SET status = 'paused' WHERE status IN ('running','pending')")
            conn.commit()
            print(f"[Startup] 崩溃恢复: {len(stale)} 个未完成任务已置为 paused: {[s[1][:20] for s in stale]}")
    except Exception as e:
        print(f"[Startup] 崩溃恢复扫描失败: {e}")

    print(f"[Startup] 已注册 {len(tool_registry.list_all())} 个工具: {tool_registry.list_names()}")
    print(f"[Startup] 已加载 {len(skill_registry.list_all())} 个技能")

    # Curator 自动归档
    try:
        from tars.skills.curator import skill_curator
        from tars.config.skills import skills_config
        if skill_curator and skills_config.auto_archive_days:
            archived = skill_curator.check_auto_archive(days=skills_config.auto_archive_days)
            if archived:
                print(f"[Startup] Curator 自动归档 {len(archived)} 个闲置技能: {archived}")
    except Exception as e:
        print(f"[Startup] Curator 自动归档扫描失败: {e}")

    # SSE sticky 检测
    workers = int(os.getenv("WEB_CONCURRENCY", "1") or "1")
    uvicorn_workers = int(os.getenv("UVICORN_WORKERS", "0") or "0")
    sticky_ok = os.getenv("TARS_SSE_STICKY", "").lower() in ("1", "true", "yes")
    if not sticky_ok and max(workers, uvicorn_workers) > 1:
        print(
            "[Startup] ERROR: InsightForge SSE requires uvicorn --workers 1 or Ingress sticky session. "
            "Set TARS_SSE_STICKY=1 if sticky is configured. See docs/04-运维文档/insightforge-deploy.md"
        )


async def run_shutdown(shutdown_scheduler, connection_manager=None):
    """执行所有关闭清理（被 main.py 的 @app.on_event("shutdown") 调用）。

    v5.0.5/P5 优雅关闭：每步独立 try/except + 整体超时，确保单步失败或卡住
    不会阻塞进程退出。
    """
    import asyncio
    import logging

    logger = logging.getLogger("tars.lifespan")

    async def _graceful():
        # 1) 先断开所有 WebSocket（通知客户端"即将下线"，可重连到新实例）
        if connection_manager is not None:
            try:
                closed = await connection_manager.disconnect_all()
                logger.info("graceful shutdown: closed %s websocket(s)", closed)
            except Exception:
                logger.exception("disconnect_all failed during shutdown")

        # 2) 停止调度器（不再触发新任务）
        try:
            await shutdown_scheduler()
        except Exception:
            logger.exception("shutdown_scheduler failed")

        # 3) 关闭 ASR 池
        try:
            from tars.meeting.asr.pool import shutdown_asr_pool

            shutdown_asr_pool()
        except Exception:
            logger.exception("shutdown_asr_pool failed")

        # 4) 关闭出站 HTTP 连接池
        try:
            from tars.models.connection_pool import close_connection_pool

            await close_connection_pool()
        except Exception:
            logger.exception("close_connection_pool failed")

    try:
        await asyncio.wait_for(_graceful(), timeout=30)
    except asyncio.TimeoutError:
        logger.warning("graceful shutdown exceeded 30s timeout; forcing exit")
