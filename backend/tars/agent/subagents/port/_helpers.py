"""港航 Agent 公共 execute 逻辑。"""
import json
from typing import Any, Dict


def build_user_content(task: str, context: Dict[str, Any] | None) -> str:
    ctx = context or {}
    domain = ctx.get("domain_memory", "")
    shared = ctx.get("shared", {})
    shared_text = json.dumps(shared, ensure_ascii=False, indent=2) if shared else "（空）"
    parts = []
    if domain:
        parts.append(f"领域记忆:\n{domain}")
    parts.append(f"协作黑板:\n{shared_text}")
    parts.append(f"任务:\n{task}")
    return "\n\n".join(parts)


async def run_port_agent(agent, task: str, context: Dict[str, Any] | None, fallback_label: str) -> str:
    from ....models.base import ChatMessage

    ctx = context or {}
    prompt = agent.merge_with_personality(ctx.get("personality"))
    user_content = build_user_content(task, ctx)
    if agent.llm_provider:
        resp = await agent.llm_provider.chat(
            [
                ChatMessage(role="system", content=prompt),
                ChatMessage(role="user", content=user_content),
            ],
            stream=False,
        )
        return resp.content if hasattr(resp, "content") else str(resp)
    return f"[{fallback_label}] 待 LLM: {task}"
