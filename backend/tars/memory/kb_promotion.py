"""记忆要点 → 知识库升格（批量合成，非碎片直写）。"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .turn_knowledge_publisher import publish_synthesized_note

if TYPE_CHECKING:
    from .manager import MemoryManager

from ..config.memory import config

# 升格阈值（性能 vs 知识密度平衡）
MIN_ITEMS_FOR_AUTO_PROMOTE = 3
MIN_CHARS_FOR_AUTO_PROMOTE = 800
MAX_ITEMS_PER_NOTE = 20

SYNTHESIS_PROMPT = """将以下多条「对话记住要点」合成为一篇可入库的知识库笔记。

要求：
1. 使用 Markdown
2. 结构：标题、背景（1 段）、核心要点（有序列表）、注意事项（如有）
3. 去重、合并相近条目，保留技术细节（配置、命令、根因、方案）
4. 不要编造未出现的信息
5. 只输出 Markdown 正文，不要代码围栏包裹全文

背景问题：
{user_context}

要点列表：
{bullets}
"""


def default_promotion_group_id(tenant_id: str, when: Optional[datetime] = None) -> str:
    dt = when or datetime.now(timezone(timedelta(hours=8)))
    return f"manual-{tenant_id}-{dt.strftime('%Y-%m-%d')}"


def _bullet_lines(items: List[Dict[str, Any]]) -> str:
    lines = []
    for idx, item in enumerate(items, start=1):
        category = item.get("category") or "fact"
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"{idx}. [{category}] {content}")
    return "\n".join(lines)


def synthesize_note_markdown(
    items: List[Dict[str, Any]],
    *,
    user_context: str = "",
    provider=None,
) -> str:
    bullets = _bullet_lines(items)
    if provider:
        try:
            import asyncio
            from ..models import ChatMessage

            async def _call():
                messages = [
                    ChatMessage(role="system", content="你是技术文档整理助手。"),
                    ChatMessage(
                        role="user",
                        content=SYNTHESIS_PROMPT.format(
                            user_context=user_context or "（无）",
                            bullets=bullets,
                        ),
                    ),
                ]
                resp = await provider.chat(messages, stream=False, temperature=0.2)
                text = resp.content if hasattr(resp, "content") else str(resp)
                text = text.strip()
                if text.startswith("```"):
                    text = re.sub(r"^```(?:markdown)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)
                return text.strip()

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中（FastAPI）由调用方 await
                raise RuntimeError("use async_synthesize_note_markdown in async context")
            return loop.run_until_complete(_call())
        except RuntimeError:
            raise
        except Exception as e:
            print(f"[KBPromotion] LLM 合成失败，使用模板 fallback: {e}")

    title = f"对话精华 {datetime.now().strftime('%Y-%m-%d')}"
    parts = [f"# {title}", ""]
    if user_context.strip():
        parts.extend(["## 背景", user_context.strip(), ""])
    parts.append("## 核心要点")
    for item in items:
        content = str(item.get("content") or "").strip()
        category = item.get("category") or "fact"
        if content:
            parts.append(f"- [{category}] {content}")
    return "\n".join(parts)


async def async_synthesize_note_markdown(
    items: List[Dict[str, Any]],
    *,
    user_context: str = "",
    provider=None,
) -> str:
    bullets = _bullet_lines(items)
    if provider:
        try:
            from ..models import ChatMessage

            messages = [
                ChatMessage(role="system", content="你是技术文档整理助手。"),
                ChatMessage(
                    role="user",
                    content=SYNTHESIS_PROMPT.format(
                        user_context=user_context or "（无）",
                        bullets=bullets,
                    ),
                ),
            ]
            resp = await provider.chat(messages, stream=False, temperature=0.2)
            text = resp.content if hasattr(resp, "content") else str(resp)
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:markdown)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            if len(text) >= 80:
                return text
        except Exception as e:
            print(f"[KBPromotion] LLM 合成失败，使用模板 fallback: {e}")

    return synthesize_note_markdown(items, user_context=user_context, provider=None)


def group_ready(stats: Dict[str, Any]) -> bool:
    return (
        stats.get("count", 0) >= MIN_ITEMS_FOR_AUTO_PROMOTE
        or stats.get("total_chars", 0) >= MIN_CHARS_FOR_AUTO_PROMOTE
    )


async def promote_group_to_kb(
    manager: "MemoryManager",
    group_id: str,
    *,
    user_context: str = "",
    memory_ids: Optional[List[str]] = None,
) -> Optional[str]:
    """将一组 pending 记忆合成一篇 KB 文档。返回 doc_id。"""
    db = manager.db
    tenant_id = manager.tenant_id
    rows = db.list_memories_for_kb_promotion(
        tenant_id=tenant_id,
        promotion_group_id=group_id,
        memory_ids=memory_ids,
        limit=MAX_ITEMS_PER_NOTE,
    )
    if not rows:
        return None

    items = [
        {"content": m.content, "category": m.category, "memory_id": m.id}
        for m in rows
    ]
    markdown = await async_synthesize_note_markdown(
        items,
        user_context=user_context,
        provider=manager.provider,
    )
    title_hint = markdown.splitlines()[0].lstrip("# ").strip() if markdown else f"对话精华-{group_id[-10:]}"
    if not config.turn_publisher_enabled:
        return None
    doc_id = publish_synthesized_note(
        db=db,
        vector_store=manager.vector_store,
        embedding_provider=manager.embedding_provider,
        tenant_id=tenant_id,
        title=title_hint[:80],
        markdown=markdown,
        source_memory_ids=[m.id for m in rows],
    )
    if not doc_id:
        return None

    db.mark_memories_kb_published(
        [m.id for m in rows],
        tenant_id=tenant_id,
        kb_doc_id=doc_id,
    )
    return doc_id


async def maybe_auto_promote_group(manager: "MemoryManager", group_id: str) -> Optional[str]:
    """阈值触发：组内要点足够多时自动升格（后台 / 保存后调用）。"""
    if not config.kb_promotion_enabled:
        return None
    stats = manager.db.get_kb_promotion_group_stats(manager.tenant_id, group_id)
    if not group_ready(stats):
        return None
    return await promote_group_to_kb(manager, group_id)


async def run_scheduled_kb_promotion(base_manager: "MemoryManager") -> Dict[str, Any]:
    """Cron 扫描所有租户 pending 组并升格。"""
    if not config.kb_promotion_enabled:
        return {"promoted": 0, "skipped": 0, "doc_ids": []}
    db = base_manager.db
    promoted = 0
    skipped = 0
    doc_ids: List[str] = []

    for tenant_id, group_id in db.list_kb_promotion_groups(limit=200):
        scoped = base_manager.for_tenant(tenant_id)
        if base_manager.provider:
            scoped.set_provider(base_manager.provider)
        stats = db.get_kb_promotion_group_stats(tenant_id, group_id)
        if not group_ready(stats):
            skipped += 1
            continue
        doc_id = await promote_group_to_kb(scoped, group_id)
        if doc_id:
            promoted += 1
            doc_ids.append(doc_id)
        else:
            skipped += 1

    return {"promoted": promoted, "skipped": skipped, "doc_ids": doc_ids}
