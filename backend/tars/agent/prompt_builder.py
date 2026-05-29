"""PortMeta Agent Prompt Builder — System prompt 拼装逻辑（从 agent.py 拆分）。"""

from typing import List, Optional
from ..workspace import WorkspaceManager


def build_system_prompt(agent, user_content: str, session_id: str,
                         tenant_id: str, memory_context: str,
                         scoped_memory_manager, cmd_result,
                         knowledge_context: str = "") -> str:
    """Build the full system prompt for a conversation turn (uncached fallback)."""
    return build_static_prompt(agent, user_content, session_id, cmd_result, tenant_id) + \
           build_memory_prompt(agent, memory_context, knowledge_context)


def build_static_prompt(agent, user_content: str, session_id: str,
                         cmd_result, tenant_id: str = "default") -> str:
    """Build cacheable static parts: persona + tools + skill list."""
    ws = WorkspaceManager.for_tenant(tenant_id)
    sp = ws.build_context()
    overlay = ws.load_prompt_overlays()
    if overlay:
        sp += f"\n\n{overlay}"

    # 渐进披露 + SkillRouter 按需注入（tenant 过滤）
    if hasattr(agent, 'skill_loader') and hasattr(agent.skill_loader, 'get_progressive_disclosure'):
        disclosure = agent.skill_loader.get_progressive_disclosure(tenant_id)
        if disclosure:
            sp += f"\n\n{disclosure}"

        matched = getattr(agent, "_current_matched_skills", None)
        if matched is None:
            matched = route_skills_for_message(agent, user_content, tenant_id)
        if matched and agent.skill_router:
            intent = agent.skill_router._intent_extractor.extract(user_content)
            candidates = agent.skill_router.match(intent, tenant_id=tenant_id)
            recommendations = agent.skill_router.build_recommendations(candidates)
            if recommendations:
                sp += f"\n\n{recommendations}"
            record_routing_candidates(agent, session_id, candidates)
        if matched:
            injection = build_skill_injection(agent, matched)
            if injection:
                sp += f"\n\n{injection}"
            record_skill_activations(agent, matched, session_id=session_id)
        elif hasattr(agent, '_active_skill_id') and agent._active_skill_id:
            active_skill = agent.skill_registry.get(agent._active_skill_id, tenant_id)
            if active_skill and active_skill.prompt_template:
                sp += f"\n\n## 已激活技能: {active_skill.name}\n{active_skill.prompt_template}"
    else:
        skill_injection = agent.skill_executor.build_prompt_injection()
        if skill_injection:
            sp += f"\n\n{skill_injection}"

    # 知识库规则
    sp += (
        "\n\n## 知识库使用规则\n"
        "回答用户问题前，如果问题涉及项目信息、历史决策、会议内容、技术方案或业务知识，"
        "请先调用 knowledge_search 工具检索相关资料。优先使用知识库中的内容回答，而非凭记忆推测。\n"
        "引用知识库内容时，在相关陈述句末标注 [ref:doc_id|文档标题]（doc_id 与标题来自检索结果中的 ref: 与来源字段）。"
    )

    if agent.wiki_store:
        wiki_index = agent.wiki_store.read_index()
        if wiki_index.strip() and wiki_index != "# Wiki Index\n\n":
            sp += (
                "\n\n## 你的知识 Wiki\n"
                "以下是你维护的结构化知识库索引。查阅用 read_wiki，用户要求写入/更新 wiki 时用 write_wiki：\n\n"
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


def route_skills_for_message(agent, user_content: str, tenant_id: str = "default",
                              scene_intent: Optional[str] = None,
                              scene_keywords: Optional[List[str]] = None):
    from ..config.skills import skills_config
    if not skills_config.router_enabled:
        if hasattr(agent, 'skill_loader'):
            text = agent.skill_loader.get_contextual_skill_injection(user_content, tenant_id=tenant_id)
            if not text:
                return []
        return []

    if agent.skill_router:
        return agent.skill_router.route_from_content(
            user_content,
            tenant_id=tenant_id,
            scene_intent=scene_intent,
            scene_keywords=scene_keywords,
        )

    if hasattr(agent, 'skill_loader'):
        skills = agent.skill_loader.skill_registry.list_prompt_skills(tenant_id) if agent.skill_loader.skill_registry else []
        content_lower = user_content.lower()
        scored = []
        for skill in skills:
            score = agent.skill_loader._score_skill_relevance(skill, content_lower)
            if score > 0:
                scored.append((skill, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:3]
    return []


def build_skill_injection(agent, matched) -> str:
    if agent.skill_router:
        return agent.skill_router.build_injection(matched)
    sections = []
    for skill, _ in matched:
        if skill.prompt_template:
            sections.append(f"## 已激活技能: {skill.name}\n{skill.prompt_template}")
    return "\n\n".join(sections)


def record_skill_activations(agent, matched, session_id: str = "default") -> None:
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


def record_routing_candidates(agent, session_id: str, candidates) -> None:
    try:
        from ..database.skill_routing_store import get_skill_routing_store
        store = get_skill_routing_store()
        if store and candidates:
            store.record_recommendations(session_id, candidates)
    except Exception:
        pass


def build_memory_prompt(agent, memory_context: str, knowledge_context: str = "") -> str:
    """Build dynamic per-query part: memory + knowledge search results."""
    parts = []
    if knowledge_context:
        parts.append(f"## 知识库检索结果\n{knowledge_context}")
    if memory_context:
        parts.append(memory_context)
    if not parts:
        return ""
    return "\n\n" + "\n\n".join(parts)


async def build_knowledge_context(agent, user_content: str, tenant_id: str,
                                   channel, session_id: str) -> str:
    """Proactively retrieve knowledge base snippets for the user message."""
    if not agent.knowledge_retriever or not agent.db:
        return ""
    try:
        from ..knowledge.access import search_knowledge
        from datetime import datetime, timezone, timedelta

        await channel.send(session_id, {
            "type": "thinking_step",
            "session_id": session_id,
            "step": "📚",
            "title": "检索知识库",
            "detail": user_content[:30] + ("..." if len(user_content) > 30 else ""),
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        })
        text, results = search_knowledge(
            agent.db,
            agent.knowledge_retriever,
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
