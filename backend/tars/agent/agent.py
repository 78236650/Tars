"""TARS Agent v2 - 使用 ToolDispatcher 的新 Agent"""
import os
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from ..models import LLMProvider, OllamaProvider, ChatMessage
from ..database import Database
from ..memory import MemoryManager
from ..channels import Channel
from ..workspace import WorkspaceManager
from ..tools import ToolRegistry, ToolDispatcher, registry as global_tool_registry
from ..skills import SkillRegistry, skill_registry as global_skill_registry, SkillExecutor
from .subagent_manager import SubAgentManager
from .handoff import HandoffManager


MULTIMODAL_MODELS = ["llava", "bakllava", "llama3.2-vision", "minicpm-v", "qwen2-vl", "qwen-vl"]


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class AgentV2:
    """重构后的 Agent，使用 ToolDispatcher 进行工具调用"""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        db: Optional[Database] = None,
        workspace: Optional[WorkspaceManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        skill_registry: Optional[SkillRegistry] = None,
        file_storage=None,
        file_parser=None,
        memory_manager=None,
        task_executor=None,
        knowledge_retriever=None,
        evolution_manager=None,
        wiki_store=None,
    ):
        self.db = db or Database()
        self.workspace = workspace or WorkspaceManager()
        self.current_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.subagent_manager = SubAgentManager(self)
        self.handoff_manager = HandoffManager()
        from .follow_up_queue import FollowUpQueue
        self.follow_up_queue = FollowUpQueue()
        self.evolution_manager = evolution_manager

        self.tool_registry = tool_registry or global_tool_registry
        self.skill_registry = skill_registry or global_skill_registry
        self.skill_executor = SkillExecutor(self.skill_registry)

        self.file_storage = file_storage
        self.file_parser = file_parser
        self.task_executor = task_executor
        self.knowledge_retriever = knowledge_retriever
        self.wiki_store = wiki_store

        # 斜杠命令系统
        from ..commands import CommandRegistry, CommandParser
        from ..commands.builtin import register_all
        self.command_registry = CommandRegistry()
        register_all(self.command_registry)
        self.command_parser = CommandParser(self.command_registry)
        self._active_mode: Optional[str] = None  # "plan" | "yolo" | "brainstorm" | None

        # v2.2 Working Context + Scene Analyzer（异步，不接主流程）
        from ..memory.working_context import WorkingContextManager
        from ..config.memory import config as mem_config
        self.wc_manager = WorkingContextManager(self.db)
        self.mem_config = mem_config
        self._pending_scene_ids = {}  # session_id -> (user_msg, assistant_msg)

        if provider:
            self.provider = provider
        else:
            self.provider = self._create_default_provider()

        # 记忆管理器（新版，支持 LLM 提取 + 语义搜索）
        self.memory_manager = memory_manager or MemoryManager(self.db, provider=self.provider)

        # v2.2 MemoryRouter + SkillRouter（feature flag 控制，依赖 memory_manager）
        if self.mem_config.router_enabled:
            from ..memory.router import MemoryRouter
            self.memory_router = MemoryRouter(self.db, self.memory_manager.embedding_provider)
        else:
            self.memory_router = None
        if self.mem_config.skill_router_enabled:
            from ..skills.router import SkillRouter
            from ..config.skills import skills_config
            embed = getattr(self.memory_manager, "embedding_provider", None)
            self.skill_router = SkillRouter(
                self.skill_registry,
                skills_config,
                embedding_provider=embed,
            )
        else:
            self.skill_router = None

        self.dispatcher = ToolDispatcher(self.tool_registry, self.provider)

    def _create_default_provider(self) -> LLMProvider:
        return OllamaProvider(model=self.current_model)

    def switch_model(self, model_name: str, provider_name: str = None) -> bool:
        """Switch model. Optionally switch provider by name."""
        try:
            if provider_name:
                from ..models import providers
                provider = providers.get(provider_name)
                if provider:
                    self.provider = provider
                    self.current_model = model_name
                    self.dispatcher.set_provider(self.provider)
                    return True
            from ..models import OllamaProvider
            if not isinstance(self.provider, OllamaProvider):
                self.provider = OllamaProvider(model=model_name)
            else:
                self.provider.model = model_name
            self.current_model = model_name
            self.dispatcher.set_provider(self.provider)
            return True
        except Exception:
            return False

    async def get_available_models(self) -> List[str]:
        try:
            return await self.provider.list_models()
        except Exception:
            return []

    async def _abort_if_cancelled(
        self,
        channel: Channel,
        session_id: str,
        *,
        partial_response: str = "",
    ) -> bool:
        if not self.follow_up_queue.is_cancelled(session_id):
            return False
        if partial_response.strip():
            self.db.add_message(session_id, "assistant", partial_response)
        await channel.send(session_id, {
            "type": "thinking_complete",
            "session_id": session_id,
            "timestamp": now_iso(),
        })
        await channel.send(session_id, {
            "type": "generation_stopped",
            "session_id": session_id,
            "reason": "user_cancelled",
            "timestamp": now_iso(),
        })
        return True

    async def handle_message(
        self,
        session_id: str,
        user_content: str,
        channel: Channel,
        file_ids: Optional[List[str]] = None,
        tenant_context: Optional[Any] = None,
        request_context: Optional[Dict[str, Any]] = None,
    ):
        """处理用户消息 - 使用 ToolDispatcher，支持文件附件和斜杠命令"""
        tenant_id = tenant_context.tenant_id if tenant_context else "default"
        turn_tool_results: List[Dict[str, Any]] = []
        turn_subagent: Optional[str] = None
        scoped_memory_manager = tenant_context.memory_manager if tenant_context else self.memory_manager
        scoped_wc_manager = type(self.wc_manager)(self.db, tenant_id=tenant_id) if hasattr(self, "wc_manager") else None
        scoped_memory_router = self.memory_router.for_tenant(tenant_id) if self.memory_router else None

        # v4.0.0: 提示词注入检测
        try:
            from ..security.injection_guard import injection_guard
            result = injection_guard.scan(user_content)
            if result.is_injection and result.severity == "high":
                await channel.send(session_id, {
                    "type": "warning",
                    "session_id": session_id,
                    "message": f"检测到潜在提示词注入（{result.severity}），输入已被拒绝。",
                    "timestamp": now_iso(),
                })
                return
        except Exception:
            pass  # 安全模块不可用时静默放行

        # 0. 拦截斜杠命令
        cmd_result = self.command_parser.execute(user_content)
        new_sid = None

        if cmd_result:
            # 设置活跃模式
            cmd_name = user_content.strip().split()[0][1:] if user_content.startswith("/") else ""
            if cmd_name in ("plan", "yolo", "brainstorm"):
                self._active_mode = cmd_name
            elif cmd_name == "clear":
                self._active_mode = None

            # 处理 action
            if cmd_result.action == "new_session":
                new_session = self.db.create_session(tenant_id=tenant_id)
                new_sid = new_session.id
                session_id = new_sid
                await channel.send(session_id, {
                    "type": "session_changed",
                    "session_id": session_id,
                    "new_session_id": new_sid,
                    "timestamp": now_iso(),
                })
            elif cmd_result.action == "invoke_subagent":
                agent_type = cmd_result.action_params.get("agent_type", "")
                task = cmd_result.action_params.get("task", "")
                turn_subagent = agent_type
                try:
                    self.db.add_message(session_id, "user", user_content)
                    sub_result = await self.subagent_manager.invoke_subagent(agent_type, task)
                    handoff = self.handoff_manager.create_pending(
                        parent_session_id=session_id,
                        subagent_type=agent_type,
                        task_summary=task,
                        full_result=sub_result,
                    )
                    await channel.send(session_id, {
                        "type": "subagent_handoff",
                        **handoff.to_ws_payload(),
                        "timestamp": now_iso(),
                    })
                    await channel.send(session_id, {
                        "type": "done",
                        "session_id": session_id,
                        "timestamp": now_iso(),
                        "model": self.current_model,
                    })
                    return
                except Exception as e:
                    await channel.send(session_id, {
                        "type": "error", "session_id": session_id,
                        "message": f"子代理调用失败: {e}", "code": "subagent_error",
                        "timestamp": now_iso(),
                    })
                    return
            elif cmd_result.action == "skill_permissions":
                skill_id = cmd_result.action_params.get("skill_id", "")
                try:
                    from ..skills.permission_engine import permission_engine
                    declared = permission_engine.get_declared_permissions(skill_id)
                    granted = permission_engine.get_skill_permissions(skill_id)
                    lines = [f"技能 {skill_id} 权限:", f"声明: {', '.join(sorted(declared)) or '无'}",
                             f"已授权: {', '.join(sorted(granted)) or '无'}"]
                    cmd_result.frontend_message = "\n".join(lines)
                except Exception as e:
                    cmd_result.frontend_message = f"❌ 查询失败: {e}"

            elif cmd_result.action == "skill_find":
                query = cmd_result.action_params.get("query", "")
                try:
                    from ..skillhub.local_catalog import LocalSkillCatalog
                    from pathlib import Path
                    project_dir = Path(__file__).resolve().parent.parent.parent
                    catalog = LocalSkillCatalog(
                        catalog_path=str(project_dir / "data" / "skillhub_catalog.json"),
                        bundle_dir=str(project_dir / "data" / "skillhub" / "skills"),
                    )
                    results = catalog.search(query)[:5]
                    if not results:
                        cmd_result.frontend_message = f"未找到与「{query}」相关的技能。请打开 工具→SkillHub 浏览。"
                    else:
                        lines = [f"🔍 SkillHub 推荐（{query}）:"]
                        for pkg in results:
                            lines.append(f"- **{pkg.name}** (`{pkg.id}`) — {pkg.description[:50]}")
                        lines.append("\n在 工具→SkillHub 点击安装，或说 `/skill <技能id>` 激活已安装技能。")
                        cmd_result.frontend_message = "\n".join(lines)
                except Exception as e:
                    cmd_result.frontend_message = f"搜索失败: {e}"

            elif cmd_result.action == "skill_disable":
                skill_id = cmd_result.action_params.get("skill_id", "")
                if skill_id:
                    skill = self.skill_registry.get(skill_id)
                    if skill:
                        self.skill_registry.disable(skill.id)
                        if self.skill_router:
                            self.skill_router.force_off(skill.id)
                    cmd_result.frontend_message = f"🔕 技能 {skill_id} 已关闭"
                else:
                    self._active_skill_id = None
                    if self.skill_router:
                        self.skill_router.clear_sticky()
                    cmd_result.frontend_message = "🔕 已清除 sticky 技能"

            elif cmd_result.action == "skill_revoke":
                skill_id = cmd_result.action_params.get("skill_id", "")
                perm = cmd_result.action_params.get("permission", "")
                try:
                    from ..skills.permission_engine import permission_engine
                    ok = permission_engine.revoke_permission(skill_id, perm)
                    cmd_result.frontend_message = f"{'✅' if ok else '❌'} 已撤销 {skill_id} 的 {perm} 权限"
                except Exception as e:
                    cmd_result.frontend_message = f"❌ 撤销失败: {e}"

            elif cmd_result.action == "activate_skill":
                skill_id = cmd_result.action_params.get("skill_id", "")
                # 设置活跃技能（用于权限检查）
                self._active_skill_id = skill_id
                skill = self.skill_registry.get(skill_id)
                if not skill:
                    for s in self.skill_registry.list_all():
                        if s.name == skill_id or skill_id in s.id:
                            skill = s
                            break
                if skill:
                    self.skill_registry.enable(skill.id)
                    self._active_skill_id = skill.id
                    if self.skill_router:
                        self.skill_router.force_sticky(skill.id)
                    cmd_result.frontend_message = f"⚡ 技能 {skill.name} 已激活（sticky）✓"
                    await channel.send(session_id, {
                        "type": "thinking_step",
                        "session_id": session_id,
                        "step": "⚡",
                        "title": f"激活技能: {skill.name}",
                        "timestamp": now_iso(),
                    })
                else:
                    cmd_result.frontend_message = f"❌ 技能 {skill_id} 不存在"

            # 发送前端消息
            if cmd_result.frontend_message:
                await channel.send(session_id, {
                    "type": "command_result",
                    "session_id": session_id,
                    "command": user_content.split()[0] if user_content.startswith("/") else "",
                    "message": cmd_result.frontend_message,
                    "timestamp": now_iso(),
                })

            # /help 和 /clear 不调用 LLM
            if cmd_result.action in ("new_session",) or (not cmd_result.prompt_injection and cmd_result.frontend_message and cmd_result.action != "invoke_subagent"):
                self.db.add_message(session_id, "user", user_content)
                self.db.add_message(session_id, "assistant", cmd_result.frontend_message)
                await channel.send(session_id, {
                    "type": "done", "session_id": session_id,
                    "timestamp": now_iso(), "model": self.current_model,
                })
                return

        # 0.5 发送处理开始事件
        await channel.send(session_id, {
            "type": "thinking_start",
            "session_id": session_id,
            "timestamp": now_iso(),
        })

        # 1. 获取或创建会话
        session = self.db.get_session(session_id, tenant_id=tenant_id)
        if not session:
            session = self.db.create_session(tenant_id=tenant_id)
            session_id = session.id

        # 2. 保存用户消息
        self.db.add_message(session_id, "user", user_content)

        # 3. 获取历史消息
        history = self.db.get_messages(session_id)

        # 4. 获取记忆上下文（v2.2: 优先 MemoryRouter，否则老路）
        if scoped_memory_router and self.mem_config.router_enabled and scoped_wc_manager:
            await channel.send(session_id, {
                "type": "thinking_step",
                "session_id": session_id,
                "step": "🧠",
                "title": "检索相关记忆",
                "detail": user_content[:30] + ("..." if len(user_content) > 30 else ""),
                "timestamp": now_iso(),
            })
            wc = scoped_wc_manager.get(session_id)
            ctx = scoped_memory_router.retrieve(user_content, wc)
            router_injection = scoped_memory_router.build_injection(ctx)
            # v4.1.5: MemoryRouter 不读 core_memory（persona/user_profile/...），
            # 单独问"我是谁"这类问题需要它，因此始终把 core 块拼到前面。
            core_render = ""
            try:
                if scoped_memory_manager and getattr(scoped_memory_manager, "core", None):
                    core_render = scoped_memory_manager.core.render_for_prompt().strip()
            except Exception:
                core_render = ""
            memory_context = "\n\n".join(p for p in [core_render, router_injection] if p)
            if wc:
                memory_context = f"## 当前意图: {wc.get('current_intent','unknown')}\n\n{memory_context}"
        else:
            memory_context = scoped_memory_manager.get_context_for_query(user_content)

        # 4.5 自动检索知识库（不依赖模型是否主动调用 knowledge_search）
        knowledge_context = await self._build_knowledge_context(user_content, tenant_id, channel, session_id)

        # 4.9 每轮消息重新路由技能（不可缓存，需实时匹配）
        scene_intent = None
        scene_keywords: List[str] = []
        if scoped_wc_manager:
            try:
                wc = scoped_wc_manager.get(session_id)
                if wc:
                    scene_intent = wc.get("current_intent") or (wc.get("last_scene_snapshot") or {}).get("intent")
                    scene_keywords = list(wc.get("recall_hints") or [])
            except Exception:
                pass

        matched_skills = self._route_skills_for_message(
            user_content,
            tenant_id,
            scene_intent=scene_intent,
            scene_keywords=scene_keywords,
        ) or []
        self._current_matched_skills = matched_skills
        skills_payload = [{"id": s.id, "name": s.name} for s, _ in matched_skills]
        if not skills_payload and getattr(self, "_active_skill_id", None):
            active_skill = self.skill_registry.get(self._active_skill_id, tenant_id)
            if active_skill:
                skills_payload = [{"id": active_skill.id, "name": active_skill.name}]
        self._last_routed_skills = skills_payload

        # 5. 构建 system prompt（含人格 + 记忆 + 渐进披露技能 + 命令提示词）
        # v4.0.0: cache static parts (persona + tools + skills), rebuild memory per query
        try:
            from ..cache.prompt_cache import prompt_cache, hash_key
            if prompt_cache:
                _static_key = hash_key("sys_static", tenant_id)
                static_part = prompt_cache.get_or_compute(
                    _static_key,
                    lambda: self._build_static_prompt(
                        user_content, session_id, cmd_result, tenant_id,
                    ),
                )
                dynamic_part = self._build_memory_prompt(memory_context, knowledge_context)
                system_prompt = static_part + dynamic_part
            else:
                system_prompt = self._build_system_prompt(
                    user_content, session_id, tenant_id,
                    memory_context, scoped_memory_manager, cmd_result,
                    knowledge_context=knowledge_context,
                )
        except Exception:
            system_prompt = self._build_system_prompt(
                user_content, session_id, tenant_id,
                memory_context, scoped_memory_manager, cmd_result,
                knowledge_context=knowledge_context,
            )

        skills_payload = list(getattr(self, "_last_routed_skills", []) or [])
        await channel.send(session_id, {
            "type": "skills_active",
            "session_id": session_id,
            "skills": skills_payload,
            "timestamp": now_iso(),
        })
        self._last_routed_skills = []

        # 6. 构建消息列表
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # 7. 处理文件附件
        if file_ids and self.file_storage and self.file_parser:
            await channel.send(session_id, {
                "type": "file_processing",
                "session_id": session_id,
                "message": "正在解析文件...",
                "timestamp": now_iso(),
            })
            await channel.send(session_id, {
                "type": "thinking_step",
                "session_id": session_id,
                "step": "📦",
                "title": "解析文件附件",
                "detail": f"{len(file_ids)} 个文件",
                "timestamp": now_iso(),
            })
            user_msg = await self._build_message_with_files(session_id, user_content, file_ids, channel)
            messages[-1] = user_msg  # 替换最后一条用户消息

        # 8. 定义工具调用回调
        used_web_flag = {"value": False}

        async def on_tool_call(tool_name: str, arguments: Dict):
            # v2.5: 权限检查
            if hasattr(self, '_active_skill_id') and self._active_skill_id:
                from ..skills.permission_engine import permission_engine
                allowed, reason = permission_engine.can_call(self._active_skill_id, tool_name)
                if not allowed:
                    await channel.send(session_id, {
                        "type": "tool_result",
                        "session_id": session_id,
                        "tool": tool_name,
                        "success": False,
                        "output": "",
                        "error": f"权限不足: {reason}",
                        "timestamp": now_iso(),
                    })
                    return

            # 记录工具调用开始时间
            import time
            _tool_start = {tool_name: time.time()}
            on_tool_call._timers = getattr(on_tool_call, '_timers', {})
            on_tool_call._timers[tool_name] = _tool_start[tool_name]
            # 只读模式下拦截写操作
            if self._is_readonly_mode() and tool_name not in self.READONLY_TOOLS:
                await channel.send(session_id, {
                    "type": "tool_result",
                    "session_id": session_id,
                    "tool": tool_name,
                    "success": False,
                    "output": "",
                    "error": f"当前处于 {self._active_mode.upper()} 模式，{tool_name} 工具不可用。输入 /yolo 切换执行模式。",
                    "timestamp": now_iso(),
                })
                return  # 不执行工具
            if tool_name in ("web", "web_search", "web_fetch"):
                used_web_flag["value"] = True
            await channel.send(session_id, {
                "type": "tool_calling",
                "session_id": session_id,
                "tool": tool_name,
                "parameters": arguments,
                "timestamp": now_iso(),
            })
            await channel.send(session_id, {
                "type": "thinking_step",
                "session_id": session_id,
                "step": "🔧",
                "title": f"调用 {tool_name}",
                "detail": str(arguments)[:100],
                "timestamp": now_iso(),
            })

        async def on_tool_result(tool_name: str, result):
            import time
            turn_tool_results.append({"name": tool_name, "success": bool(result.success)})
            active_skill = getattr(self, "_active_skill_id", None)
            if active_skill:
                try:
                    from ..skills.curator import skill_curator
                    if skill_curator:
                        skill_curator.record_call(active_skill, success=bool(result.success))
                except Exception:
                    pass
            _timers = getattr(on_tool_call, '_timers', {})
            duration = round(time.time() - _timers.get(tool_name, time.time()), 2) if tool_name in _timers else None
            await channel.send(session_id, {
                "type": "tool_result",
                "session_id": session_id,
                "tool": tool_name,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "duration": duration,
                "timestamp": now_iso(),
            })
            await channel.send(session_id, {
                "type": "thinking_step",
                "session_id": session_id,
                "step": "🔧",
                "title": f"{tool_name}: {'✓' if result.success else '✕'}",
                "detail": (result.output or result.error or "")[:200],
                "timestamp": now_iso(),
            })

        # 8. 调用 ToolDispatcher
        await channel.send(session_id, {
            "type": "thinking_step",
            "session_id": session_id,
            "step": "💭",
            "title": "生成回答",
            "timestamp": now_iso(),
        })
        if await self._abort_if_cancelled(channel, session_id):
            return
        full_response = ""
        # v4.0.0: rate limiter
        _limiter_acquired = False
        try:
            from ..concurrency.limiter import rate_limiter
            if rate_limiter:
                _limiter_acquired = await rate_limiter.acquire(tenant_id, "llm")
                if not _limiter_acquired:
                    await channel.send(session_id, {
                        "type": "error",
                        "session_id": session_id,
                        "message": "系统繁忙，请稍后重试",
                        "code": "rate_limited",
                        "timestamp": now_iso(),
                    })
                    return
        except Exception:
            pass
        try:
            async for chunk in self.dispatcher.chat_with_tools(
                messages=messages,
                model_name=self.current_model,
                stream=True,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                tools=self._get_allowed_tool_schemas(),
                tool_context={
                    "session_id": session_id,
                    "tenant_id": tenant_id,
                    "user_role": (request_context or {}).get("user_role", "user"),
                    "user_id": (request_context or {}).get("user_id", "default"),
                    "_feedback_collector": (
                        self.evolution_manager.feedback_collector
                        if self.evolution_manager
                        else None
                    ),
                },
            ):
                if self.follow_up_queue.is_cancelled(session_id):
                    break
                full_response += chunk
                await channel.send(session_id, {
                    "type": "text_chunk",
                    "session_id": session_id,
                    "content": chunk,
                    "timestamp": now_iso(),
                    "model": self.current_model,
                })
        except Exception as e:
            err_text = str(e)
            try:
                import httpx as _httpx
                if isinstance(e, _httpx.HTTPStatusError) and e.response is not None:
                    body_excerpt = ""
                    try:
                        body_excerpt = (e.response.text or "")[:300]
                    except Exception:
                        pass
                    err_text = (
                        f"上游 LLM 返回 {e.response.status_code} "
                        f"({e.response.reason_phrase}) — url={e.request.url}; body={body_excerpt}"
                    )
            except Exception:
                pass
            await channel.send(session_id, {
                "type": "error",
                "session_id": session_id,
                "message": f"处理失败: {err_text}",
                "code": "agent_error",
                "timestamp": now_iso(),
            })
            return
        finally:
            # v4.0.0: release limiter (exception + normal path both hit finally)
            if _limiter_acquired:
                try:
                    from ..concurrency.limiter import rate_limiter
                    if rate_limiter:
                        rate_limiter.release(tenant_id, "llm")
                except Exception:
                    pass

        if await self._abort_if_cancelled(channel, session_id, partial_response=full_response):
            return

        # 8.5 检查是否有待执行的计划（task_planner 被调用时）
        if self.task_executor:
            planner_tool = self.tool_registry.get("task_planner")
            if planner_tool and hasattr(planner_tool, "pop_pending_plan"):
                plan = planner_tool.pop_pending_plan()
                if plan:
                    import json
                    import uuid
                    from ..orchestration.models import PlanStatus
                    from ..database.plan_store import get_plan_store
                    from ..orchestration.plan_gate import get_plan_gate

                    plan.id = str(uuid.uuid4())
                    plan.session_id = session_id
                    plan.tenant_id = tenant_id

                    # 解析 workspace 路径
                    from ..orchestration.workspace_resolver import resolve_workspace_path
                    ws_path, ws_source = resolve_workspace_path(session_id, title=plan.goal[:30])
                    plan.workspace_path = ws_path

                    plan_store = get_plan_store()
                    plan_store.create(plan)

                    plan_gate = get_plan_gate()
                    if plan_gate:
                        approved = await plan_gate.submit_for_review(plan, channel)
                        if not approved:
                            await channel.send(session_id, {
                                "type": "plan_review_rejected",
                                "session_id": session_id,
                                "plan_id": plan.id,
                                "timestamp": now_iso(),
                            })
                            return
                        refreshed = plan_store.get(plan.id)
                        if refreshed:
                            plan = refreshed

                    plan_store.update_status(plan.id, PlanStatus.EXECUTING)
                    plan.status = PlanStatus.EXECUTING

                    # v2.5: 先取 PDCA 配置（require_git 检查和变量替换都要用）
                    pdca_config, pdca_ref = (
                        planner_tool.pop_pending_pdca()
                        if hasattr(planner_tool, "pop_pending_pdca")
                        else (None, None)
                    )

                    # v2.5: require_git 检查
                    if pdca_config and pdca_config.workspace.get("require_git"):
                        import os as _os
                        if not _os.path.isdir(_os.path.join(ws_path, ".git")):
                            await channel.send(session_id, {
                                "type": "task_aborted",
                                "session_id": session_id,
                                "step_id": 0,
                                "error": f"技能要求 git 仓库但 {ws_path} 不是 git 目录",
                                "timestamp": now_iso(),
                            })
                            return

                    # v2.5: PDCA workspace.* 变量替换（step_N.* 保留给 executor 运行时处理）
                    skill_id_from_ref = None
                    if pdca_config:
                        from ..orchestration.variable_engine import VariableEngine
                        engine = VariableEngine(ws_path)
                        for step in plan.steps:
                            # 按 tool_name 决定 shlex.quote 作用范围
                            step.arguments = engine.resolve_dict(step.arguments, tool_name=step.tool)
                        # 从 pdca_ref 反推 skill_id，供权限检查使用
                        if pdca_ref and pdca_ref.startswith("skill://"):
                            skill_id_from_ref = pdca_ref.replace("skill://", "").split("/")[0]
                            self._active_skill_id = skill_id_from_ref
                            plan.skill_id = skill_id_from_ref

                    # 持久化任务到 SQLite
                    task_id = str(uuid.uuid4())
                    now = now_iso()
                    conn = self.db._get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO tasks (id, session_id, title, goal, workspace_path, "
                        "workspace_source, status, current_step, total_steps, artifacts, "
                        "output_summary, created_at, updated_at, completed_at, error_message, "
                        "skill_id, pdca_ref) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (task_id, session_id, plan.goal[:30], plan.goal,
                         ws_path, ws_source, "running", 0, len(plan.steps),
                         None, None, now, now, None, None,
                         skill_id_from_ref, pdca_ref),
                    )
                    for s in plan.steps:
                        cur.execute(
                            "INSERT INTO task_steps(task_id,step_order,description,tool,arguments,verify_type,verify_expected,verify_msg,expected_artifacts) "
                            "VALUES(?,?,?,?,?,?,?,?,?)",
                            (task_id, s.id, s.description, s.tool,
                             json.dumps(s.arguments, ensure_ascii=False),
                             None, None, None, None),
                        )
                    conn.commit()

                    # 发 task_created 事件
                    await channel.send(session_id, {
                        "type": "task_created",
                        "session_id": session_id,
                        "payload": {
                            "task_id": task_id,
                            "task": {
                                "id": task_id, "title": plan.goal[:30], "goal": plan.goal,
                                "workspace_path": ws_path, "workspace_source": ws_source,
                                "status": "running", "current_step": 0,
                                "total_steps": len(plan.steps),
                                "skill_id": skill_id_from_ref,
                                "pdca_ref": pdca_ref,
                                "steps": [{"id": s.id, "step_order": s.id, "description": s.description,
                                           "tool": s.tool, "status": "pending"} for s in plan.steps],
                            }
                        },
                        "timestamp": now,
                    })

                    # v2.5: 把 pdca act 配置传给 executor（若有）
                    if pdca_config and hasattr(self.task_executor, "act_policy"):
                        act = pdca_config.act or {}
                        if "max_retries" in act:
                            self.task_executor.act_policy.max_retries = act["max_retries"]
                        if "retry_backoff_s" in act:
                            self.task_executor.act_policy.retry_backoff_s = act["retry_backoff_s"]
                        if "on_final_failure" in act:
                            self.task_executor.act_policy.on_final_failure = act["on_final_failure"]

                    # 执行计划（v2.4: 危险命令检查已集成在 executor 内）
                    from ..database.audit_store import get_verification_audit_store
                    results = await self.task_executor.execute(
                        plan,
                        session_id,
                        channel,
                        workspace_path=ws_path,
                        plan_id=plan.id,
                        plan_store=plan_store,
                        skill_id=skill_id_from_ref,
                        skill_registry=self.skill_registry,
                        audit_store=get_verification_audit_store(),
                    )

                    # 采集 artifacts
                    from ..orchestration.artifacts_collector import ArtifactsCollector
                    collector = ArtifactsCollector(ws_path)
                    collector.take_snapshot()
                    artifacts = collector.collect_new_files()
                    # 补充 planner 预声明
                    for s in plan.steps:
                        artifacts.extend(ArtifactsCollector.collect_from_step({
                            "expected_artifacts": [], "arguments": s.arguments,
                        }))
                    artifacts = list(set(artifacts))

                    # output_summary: 最后成功步骤的 output 前 200 字符
                    last_output = ""
                    for s in reversed(plan.steps):
                        if s.status.value == "completed" and s.output:
                            last_output = s.output[:200]
                            break
                    output_summary = last_output or "任务完成，无显式输出"

                    cur.execute(
                        "UPDATE tasks SET status = 'completed', artifacts = ?, output_summary = ?, completed_at = ?, updated_at = ? WHERE id = ?",
                        (json.dumps(artifacts, ensure_ascii=False),
                         output_summary, now_iso(), now_iso(), task_id),
                    )
                    for s in plan.steps:
                        cur.execute(
                            "UPDATE task_steps SET status = ?, result = ?, error = ?, retries = ?, completed_at = ? WHERE task_id = ? AND step_order = ?",
                            (s.status.value, (s.output or "")[:500], s.error, s.retries,
                             now_iso(), task_id, s.id),
                        )
                    conn.commit()

                    # 发 task_completed 事件
                    await channel.send(session_id, {
                        "type": "task_completed",
                        "session_id": session_id,
                        "payload": {"task_id": task_id, "artifacts": artifacts},
                        "timestamp": now_iso(),
                    })

        # 9. 保存助手响应
        # v4.0.0: 保存前脱敏
        try:
            from ..security.sanitizer import sanitizer
            full_response = sanitizer.sanitize(full_response)
        except Exception:
            pass

        self.db.add_message(session_id, "assistant", full_response)

        # 9.5 自进化：回合 ingest（隐式信号 + 计数 + 可选 optimize）
        if self.evolution_manager:
            try:
                self.evolution_manager.ingest_turn(
                    tenant_id,
                    (request_context or {}).get("user_id", "default"),
                    session_id,
                    user_content,
                    full_response,
                    tools_used=[t["name"] for t in turn_tool_results],
                    tool_results=turn_tool_results,
                    subagent=turn_subagent,
                    skill_id=getattr(self, "_active_skill_id", None),
                )
            except Exception as exc:
                print(f"[Agent] evolution ingest_turn failed: {exc}")

        # 10. 反思记忆（V3 异步非阻塞，不延迟 done 事件）
        async def _reflect_background():
            try:
                applied = await scoped_memory_manager.reflect(
                    user_content,
                    full_response,
                    used_web=used_web_flag["value"],
                )
            except Exception as e:
                print(f"[Agent] 反思失败: {e}")
                applied = []
            if applied:
                await channel.send(session_id, {
                    "type": "thinking_step",
                    "session_id": session_id,
                    "step": "📝",
                    "title": "写入记忆",
                    "detail": f"{len(applied)} 条",
                    "timestamp": now_iso(),
                })
                await channel.send(session_id, {
                    "type": "memory_extracted",
                    "session_id": session_id,
                    "memories": [{"op": op.get("op"), "summary": str(op)[:80]} for op in applied],
                    "timestamp": now_iso(),
                })

        asyncio.create_task(_reflect_background())

        # 11. 完成
        await channel.send(session_id, {
            "type": "thinking_complete",
            "session_id": session_id,
            "timestamp": now_iso(),
        })
        await channel.send(session_id, {
            "type": "done",
            "session_id": session_id,
            "timestamp": now_iso(),
            "model": self.current_model,
        })

        # 12. v2.2: 异步 Scene Analyzer（不阻塞对话）
        if scoped_wc_manager:
            asyncio.create_task(self._run_scene_analyzer(session_id, user_content, full_response, tenant_id))

    # ========= v4.0.0: System Prompt 构建（可缓存） =========

    def _build_system_prompt(self, user_content: str, session_id: str,
                              tenant_id: str, memory_context: str,
                              scoped_memory_manager, cmd_result,
                              knowledge_context: str = "") -> str:
        """Build the full system prompt for a conversation turn (uncached fallback)."""
        return self._build_static_prompt(user_content, session_id, cmd_result, tenant_id) + \
               self._build_memory_prompt(memory_context, knowledge_context)

    def _build_static_prompt(self, user_content: str, session_id: str, cmd_result, tenant_id: str = "default") -> str:
        """Build cacheable static parts: persona + tools + skill list."""
        ws = WorkspaceManager.for_tenant(tenant_id)
        sp = ws.build_context()
        overlay = ws.load_prompt_overlays()
        if overlay:
            sp += f"\n\n{overlay}"

        # 渐进披露 + SkillRouter 按需注入（tenant 过滤）
        if hasattr(self, 'skill_loader') and hasattr(self.skill_loader, 'get_progressive_disclosure'):
            disclosure = self.skill_loader.get_progressive_disclosure(tenant_id)
            if disclosure:
                sp += f"\n\n{disclosure}"

            matched = getattr(self, "_current_matched_skills", None)
            if matched is None:
                matched = self._route_skills_for_message(user_content, tenant_id)
            if matched and self.skill_router:
                intent = self.skill_router._intent_extractor.extract(user_content)
                candidates = self.skill_router.match(intent, tenant_id=tenant_id)
                recommendations = self.skill_router.build_recommendations(candidates)
                if recommendations:
                    sp += f"\n\n{recommendations}"
                self._record_routing_candidates(session_id, candidates)
            if matched:
                injection = self._build_skill_injection(matched)
                if injection:
                    sp += f"\n\n{injection}"
                self._record_skill_activations(matched, session_id=session_id)
            elif hasattr(self, '_active_skill_id') and self._active_skill_id:
                active_skill = self.skill_registry.get(self._active_skill_id, tenant_id)
                if active_skill and active_skill.prompt_template:
                    sp += f"\n\n## 已激活技能: {active_skill.name}\n{active_skill.prompt_template}"
        else:
            skill_injection = self.skill_executor.build_prompt_injection()
            if skill_injection:
                sp += f"\n\n{skill_injection}"

        # 知识库规则
        sp += (
            "\n\n## 知识库使用规则\n"
            "回答用户问题前，如果问题涉及项目信息、历史决策、会议内容、技术方案或业务知识，"
            "请先调用 knowledge_search 工具检索相关资料。优先使用知识库中的内容回答，而非凭记忆推测。\n"
            "引用知识库内容时，在相关陈述句末标注 [ref:doc_id|文档标题]（doc_id 与标题来自检索结果中的 ref: 与来源字段）。"
        )

        if self.wiki_store:
            wiki_index = self.wiki_store.read_index()
            if wiki_index.strip() and wiki_index != "# Wiki Index\n\n":
                sp += (
                    "\n\n## 你的知识 Wiki\n"
                    "以下是你维护的结构化知识库索引，需要详细信息时使用 read_wiki 工具查阅具体页面：\n\n"
                    f"{wiki_index}\n"
                )

        sp += (
            "\n\n## 子代理审查规则\n"
            "当子代理任务完成并处于 pending_review 状态时，你必须先向用户摘要子代理结果并请求确认，"
            "在用户通过 accept 接受前，不得将子代理输出当作最终答案写入会话。"
            "用户拒绝时可说明原因并可选重新委派子代理。"
        )

        # TaskDetector
        is_slash_plan = user_content.startswith("/plan")
        try:
            from ..orchestration.detector import detect_task_intent, build_detector_prompt
            mode = detect_task_intent(user_content, is_slash_plan=is_slash_plan, session_id=session_id)
            if mode.value != "none":
                detector_prompt = build_detector_prompt(user_content, mode)
                if detector_prompt:
                    sp += f"\n\n{detector_prompt}"
        except ImportError:
            pass

        if cmd_result and cmd_result.prompt_injection:
            sp += f"\n\n{cmd_result.prompt_injection}"

        return sp

    def _route_skills_for_message(
        self,
        user_content: str,
        tenant_id: str = "default",
        scene_intent: Optional[str] = None,
        scene_keywords: Optional[List[str]] = None,
    ):
        from ..config.skills import skills_config
        if not skills_config.router_enabled:
            if hasattr(self, 'skill_loader'):
                text = self.skill_loader.get_contextual_skill_injection(user_content, tenant_id=tenant_id)
                if not text:
                    return []
                # Fallback returns text only — parse not needed, handled below
            return []

        if self.skill_router:
            return self.skill_router.route_from_content(
                user_content,
                tenant_id=tenant_id,
                scene_intent=scene_intent,
                scene_keywords=scene_keywords,
            )

        if hasattr(self, 'skill_loader'):
            # Legacy keyword fallback without router
            skills = self.skill_loader.skill_registry.list_prompt_skills(tenant_id) if self.skill_loader.skill_registry else []
            content_lower = user_content.lower()
            scored = []
            for skill in skills:
                score = self.skill_loader._score_skill_relevance(skill, content_lower)
                if score > 0:
                    scored.append((skill, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:3]
        return []

    def _build_skill_injection(self, matched) -> str:
        if self.skill_router:
            return self.skill_router.build_injection(matched)
        sections = []
        for skill, _ in matched:
            if skill.prompt_template:
                sections.append(f"## 已激活技能: {skill.name}\n{skill.prompt_template}")
        return "\n\n".join(sections)

    def _record_skill_activations(self, matched, session_id: str = "default") -> None:
        try:
            from ..skills.curator import skill_curator
            if not skill_curator:
                return
            for skill, _ in matched:
                skill_curator.record_activation(skill.id)
        except Exception:
            pass
        try:
            from ..database.skill_routing_store import get_skill_routing_store
            store = get_skill_routing_store()
            if not store:
                return
            for skill, _ in matched:
                store.mark_adopted(session_id, skill.id)
        except Exception:
            pass

    def _record_routing_candidates(self, session_id: str, candidates) -> None:
        try:
            from ..database.skill_routing_store import get_skill_routing_store
            store = get_skill_routing_store()
            if store and candidates:
                store.record_recommendations(session_id, candidates)
        except Exception:
            pass

    def _build_memory_prompt(self, memory_context: str, knowledge_context: str = "") -> str:
        """Build dynamic per-query part: memory + knowledge search results."""
        parts = []
        if knowledge_context:
            parts.append(f"## 知识库检索结果\n{knowledge_context}")
        if memory_context:
            parts.append(memory_context)
        if not parts:
            return ""
        return "\n\n" + "\n\n".join(parts)

    async def _build_knowledge_context(
        self,
        user_content: str,
        tenant_id: str,
        channel: Channel,
        session_id: str,
    ) -> str:
        """Proactively retrieve knowledge base snippets for the user message."""
        if not self.knowledge_retriever or not self.db:
            return ""
        try:
            from ..knowledge.access import search_knowledge

            await channel.send(session_id, {
                "type": "thinking_step",
                "session_id": session_id,
                "step": "📚",
                "title": "检索知识库",
                "detail": user_content[:30] + ("..." if len(user_content) > 30 else ""),
                "timestamp": now_iso(),
            })
            text, results = search_knowledge(
                self.db,
                self.knowledge_retriever,
                query=user_content,
                tenant_id=tenant_id,
                top_k=5,
            )
            if results:
                return text
            return ""
        except Exception as e:
            print(f"[Agent] 知识库自动检索失败: {e}")
            return ""

    # ========= 模式权限控制 =========

    READONLY_TOOLS = {"weather", "file", "file_list", "memory", "web_search", "web_fetch"}

    def _is_readonly_mode(self) -> bool:
        return self._active_mode in ("plan", "brainstorm")

    def _get_allowed_tool_schemas(self) -> Optional[List[Dict]]:
        """只读模式返回过滤后的工具 schema，否则返回 None（用全部）"""
        if not self._is_readonly_mode():
            return None
        return [t.to_function_schema() for t in self.tool_registry.list_all() if t.name in self.READONLY_TOOLS]

    async def _run_scene_analyzer(self, session_id: str, user_msg: str, assistant_msg: str, tenant_id: str = "default"):
        """v2.2: 异步运行 Scene Analyzer，结果写入 Working Context"""
        try:
            from ..analysis.scene_analyzer import SceneAnalyzer
            analyzer = SceneAnalyzer(self.provider, type(self.wc_manager)(self.db, tenant_id=tenant_id), self.db)
            await analyzer.analyze(session_id, user_msg, assistant_msg)
        except Exception as e:
            print(f"[Agent] SceneAnalyzer 失败: {e}")

    async def handle_subagent_handoff_action(
        self,
        handoff_id: str,
        action: str,
        *,
        channel: Optional[Channel] = None,
        connection_manager=None,
        outbound=None,
        tenant_id: str = "default",
    ) -> bool:
        """Accept or reject a pending subagent handoff and optionally push WS updates."""
        if action == "accept":
            handoff = self.handoff_manager.accept(handoff_id)
        elif action == "reject":
            handoff = self.handoff_manager.reject(handoff_id)
        else:
            return False

        if not handoff:
            return False

        session_id = handoff.parent_session_id
        event = {
            "type": "subagent_handoff",
            **handoff.to_ws_payload(),
            "timestamp": now_iso(),
        }

        async def _deliver(payload: dict) -> None:
            if channel:
                await channel.send(session_id, payload)
            elif outbound is not None:
                await outbound.send_personal(session_id, payload)
            elif connection_manager:
                await connection_manager.send_personal_message(session_id, payload)

        await _deliver(event)

        if handoff.status == "accepted":
            content = f"[subagent:{handoff.subagent_type}] {handoff.full_result}"
            self.db.add_message(session_id, "assistant", content)
            await _deliver({
                "type": "text_chunk",
                "session_id": session_id,
                "content": content,
                "timestamp": now_iso(),
                "model": self.current_model,
            })
            await _deliver({
                "type": "done",
                "session_id": session_id,
                "timestamp": now_iso(),
                "model": self.current_model,
            })
        return True

    def get_subagent_info(self) -> dict:
        return self.subagent_manager.get_all_subagents()

    def update_subagent_config(self, agent_type: str, config: dict) -> bool:
        return self.subagent_manager.update_subagent_config(agent_type, config)

    # ========= 多模态文件处理 =========

    def _is_multimodal(self) -> bool:
        model_lower = self.current_model.lower()
        return any(m in model_lower for m in MULTIMODAL_MODELS)

    async def _build_message_with_files(
        self, session_id: str, user_content: str, file_ids: List[str], channel: Channel
    ) -> Dict[str, Any]:
        """解析文件并构建带附件的用户消息"""
        text_parts = [user_content] if user_content else []
        images = []
        is_multimodal = self._is_multimodal()

        for file_id in file_ids:
            record = self.file_storage.get(file_id)
            if not record:
                text_parts.append(f"[文件 {file_id} 不存在]")
                continue

            parsed = await self.file_parser.parse(record)

            if parsed.type == "image":
                if is_multimodal and parsed.image_base64:
                    images.append(parsed.image_base64)
                else:
                    # 非多模态：发 warning + 用 OCR 文本
                    await channel.send(session_id, {
                        "type": "warning",
                        "session_id": session_id,
                        "message": "当前模型不支持图片理解，已使用 OCR 提取文字。建议切换到多模态模型（如 llava）获得更好效果。",
                        "timestamp": now_iso(),
                    })
                    if parsed.ocr_text:
                        text_parts.append(f"\n\n---\n[图片 OCR: {record.name}]\n{parsed.ocr_text}")
                    else:
                        text_parts.append(f"\n\n---\n[图片: {record.name}]（无法提取文字，建议切换到多模态模型）")
            else:
                # 文档类：附加文本
                if parsed.text:
                    truncated_note = "（内容过长已截断）" if parsed.truncated else ""
                    text_parts.append(f"\n\n---\n[文件: {record.name}]{truncated_note}\n{parsed.text}")

        content = "\n".join(text_parts)
        msg: Dict[str, Any] = {"role": "user", "content": content}
        if images:
            msg["images"] = images
        return msg
