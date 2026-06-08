"""记忆管理工具"""
from typing import Any, Dict, Optional

from tars.org import ORG_ID

from ..base import BaseTool, ToolResult


class MemoryTool(BaseTool):
    name: str = "memory"
    description: str = (
        "管理 Agent 的长期记忆。search 走语义+衰减混合检索并返回可下钻的摘要列表；"
        "detail 按 memory_id 取全文与关联 wiki 页（再用 read_wiki 取合成笔记全文）。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "search", "list", "detail", "delete"],
                "description": "操作类型",
            },
            "content": {"type": "string", "description": "记忆内容（add 时必填）"},
            "category": {"type": "string", "description": "分类: user_preference/important_decision/project_record/general"},
            "query": {"type": "string", "description": "搜索关键词（search 时必填）"},
            "memory_id": {"type": "string", "description": "记忆ID（detail/delete 时必填）"},
            "limit": {"type": "integer", "description": "返回数量限制，默认10"},
        },
        "required": ["action"],
    }

    def __init__(self, db=None, memory_manager=None):
        self.db = db
        # 注入后 search 走 HybridSearch（语义+衰减+rerank）；为空则降级为关键词检索。
        self.memory_manager = memory_manager

    def _summarize(self, m, max_chars: int = 120) -> str:
        """单条记忆的分层摘要行：暴露 id/importance/已升格 wiki 页，供 agent 决定是否下钻。"""
        content = (m.content or "").strip().replace("\n", " ")
        if len(content) > max_chars:
            content = content[:max_chars] + "…"
        imp = getattr(m, "importance", None)
        imp_str = f" imp={imp:.2f}" if isinstance(imp, (int, float)) else ""
        kb = getattr(m, "kb_doc_id", None)
        kb_str = f" wiki={kb}" if kb else ""
        return f"  - id={m.id} [{m.category}]{imp_str}{kb_str} {content}"


    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")
        content = kwargs.get("content")
        category = kwargs.get("category", "general")
        query = kwargs.get("query")
        memory_id = kwargs.get("memory_id")
        limit = kwargs.get("limit", 10)
        tenant_id = kwargs.get("tenant_id") or ORG_ID
        user_id = kwargs.get("user_id")

        if not self.db:
            return ToolResult(success=False, output="", error="数据库未初始化")

        try:
            if action == "add":
                if not content:
                    return ToolResult(success=False, output="", error="请提供记忆内容")
                mem = self.db.add_memory(
                    content,
                    category,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    scope="private",
                )
                return ToolResult(success=True, output=f"记忆已保存 (ID: {mem.id})", metadata={"memory_id": mem.id})

            elif action == "search":
                if not query:
                    return ToolResult(success=False, output="", error="请提供搜索关键词")
                # 优先走 HybridSearch（语义+衰减+rerank）；未注入时降级关键词检索。
                if self.memory_manager is not None:
                    try:
                        mgr = self.memory_manager.for_tenant(tenant_id) if tenant_id else self.memory_manager
                        memories = mgr.search.search(query, limit=limit)
                        mode = "混合检索"
                    except Exception as se:
                        memories = self.db.search_memories(query, limit, tenant_id=tenant_id, user_id=user_id)
                        mode = f"关键词检索(混合检索降级: {se})"
                else:
                    memories = self.db.search_memories(query, limit, tenant_id=tenant_id, user_id=user_id)
                    mode = "关键词检索"
                lines = [f"找到 {len(memories)} 条相关记忆（{mode}）。需详情用 action=detail+memory_id 下钻:"]
                for m in memories:
                    lines.append(self._summarize(m))
                return ToolResult(success=True, output="\n".join(lines), metadata={"count": len(memories)})

            elif action == "list":
                memories = self.db.get_recent_memories(
                    limit, tenant_id=tenant_id, user_id=user_id
                )
                lines = [f"最近 {len(memories)} 条记忆（需详情用 action=detail+memory_id 下钻）:"]
                for m in memories:
                    lines.append(self._summarize(m))
                return ToolResult(success=True, output="\n".join(lines), metadata={"count": len(memories)})

            elif action == "detail":
                if not memory_id:
                    return ToolResult(success=False, output="", error="请提供 memory_id")
                m = self.db.get_memory(memory_id, tenant_id=tenant_id)
                if not m:
                    return ToolResult(success=False, output="", error=f"记忆 {memory_id} 不存在")
                lines = [
                    f"记忆 {m.id}",
                    f"  分类: {m.category}",
                    f"  重要度: {getattr(m, 'importance', None)}",
                    f"  类型: {getattr(m, 'memory_type', None)}",
                    f"  来源: {getattr(m, 'source', None)}",
                    f"  事件时间: {getattr(m, 'event_time', None)}",
                    f"  全文: {m.content or '（内容为空）'}",
                ]
                entity_refs = getattr(m, "entity_refs", None)
                if entity_refs:
                    lines.append(f"  关联实体: {entity_refs}")
                # 双向链接：列出该记忆升格进的 wiki 页，agent 可再用 read_wiki 取合成笔记全文。
                kb = getattr(m, "kb_doc_id", None)
                if kb:
                    lines.append(f"  已升格 wiki 页: {kb}（用 read_wiki 取全文）")
                try:
                    pages = self.db.find_pages_by_memory_id(memory_id, tenant_id=tenant_id)
                    for p in pages:
                        # 仅暴露同租户页，避免跨租户引用泄露。
                        if p.get("tenant_id") not in (None, tenant_id):
                            continue
                        if p.get("page_name") != kb:
                            lines.append(f"  关联 wiki 页: {p.get('page_name')} — {p.get('title') or ''}")
                except Exception as e:
                    lines.append(f"  关联 wiki 页: 查询失败 — {e}")
                return ToolResult(
                    success=True,
                    output="\n".join(lines),
                    metadata={"memory_id": m.id, "kb_doc_id": kb},
                )

            elif action == "delete":
                if not memory_id:
                    return ToolResult(success=False, output="", error="请提供记忆ID")
                self.db.delete_memory(memory_id, tenant_id=tenant_id)
                return ToolResult(success=True, output=f"记忆 {memory_id} 已删除")

            return ToolResult(success=False, output="", error=f"未知操作: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"记忆操作失败: {e}")
