"""MemoryAwareAnalyzer — Evolution ↔ Memory 分析桥梁。

v5.0.5/A3+: 从 Memory 中拉取 correction/solution 类记忆，
聚类分析后生成 avoidance_rules 和 recommendations，
供 EvolutionOrchestrator 在 optimize 时使用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..database.base import Database


@dataclass
class MemoryPatterns:
    """分析结果"""
    avoidance_rules: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    correction_count: int = 0
    solution_count: int = 0

    @property
    def has_insights(self) -> bool:
        return bool(self.avoidance_rules or self.recommendations)


class MemoryAwareAnalyzer:
    """从 Memory 中分析模式，为 Evolution 提供数据驱动的优化建议。

    读取 correction 类记忆发现"用户反复纠正什么"，
    读取 solution 类记忆发现"用户常用什么方案"。
    """

    MIN_CORRECTIONS_FOR_RULE = 2  # 至少 2 条同类纠正才生成规则
    SOLUTION_MIN_COUNT = 2  # 至少 2 条同类方案才形成推荐

    def __init__(self, db: "Database"):
        self.db = db

    def analyze(self, tenant_id: str) -> MemoryPatterns:
        """从 Memory 中分析模式。"""
        patterns = MemoryPatterns()

        # 1. 分析 correction 类记忆 → avoidance_rules
        corrections = self._fetch_by_category(tenant_id, "correction", limit=50)
        patterns.correction_count = len(corrections)
        if corrections:
            patterns.avoidance_rules = self._cluster_corrections(corrections)

        # 2. 分析 solution 类记忆 → recommendations
        solutions = self._fetch_by_category(tenant_id, "solution", limit=50)
        patterns.solution_count = len(solutions)
        if solutions:
            patterns.recommendations = self._cluster_solutions(solutions)

        return patterns

    def _fetch_by_category(self, tenant_id: str, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        """拉取指定 category 的记忆。"""
        try:
            conn = self.db._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT id, content, category, importance, entity_refs, created_at
                   FROM memories
                   WHERE tenant_id = ? AND category = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (tenant_id, category, limit),
            )
            return [
                {
                    "id": row[0],
                    "content": row[1] or "",
                    "category": row[2] or "",
                    "importance": row[3] or 0.5,
                    "entity_refs": row[4] or "",
                    "created_at": row[5] or "",
                }
                for row in cur.fetchall()
            ]
        except Exception:
            return []

    def _cluster_corrections(self, corrections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """聚类用户纠正，生成 avoidance_rules。

        简单策略：按 content 中"纠正："后的主题词分组，
        出现超过阈值的生成一条规则。
        """
        # 提取主题关键词（"纠正：XXX" 中的 XXX 部分）
        themes: Dict[str, List[Dict]] = {}
        for c in corrections:
            content = c.get("content", "")
            # 提取"纠正："后的前30字作为主题
            if "纠正：" in content:
                theme = content.split("纠正：", 1)[1][:60].strip()
            else:
                theme = content[:60].strip()
            if not theme:
                continue
            # 用前20字做粗聚类
            key = theme[:20]
            themes.setdefault(key, []).append(c)

        rules = []
        for key, items in themes.items():
            if len(items) < self.MIN_CORRECTIONS_FOR_RULE:
                continue
            max_imp = max(item.get("importance", 0.5) for item in items)
            rules.append({
                "type": "avoidance",
                "theme": key,
                "description": f"用户反复纠正关于「{key}」的问题（{len(items)}次）",
                "correction_count": len(items),
                "importance": max_imp,
                "source_memory_ids": [item["id"] for item in items],
                "rule": f"在涉及「{key}」的话题时，优先参考最近的纠正记录，避免重复相同错误",
            })

        # 按出现次数降序
        rules.sort(key=lambda r: -r["correction_count"])
        return rules[:5]  # 最多 5 条规则

    def _cluster_solutions(self, solutions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """聚类解决方案，生成 recommendations。

        按 entity_refs 中第一个实体分组，同一实体多次出现说明该领域有成熟方案。
        """
        import json

        by_entity: Dict[str, List[Dict]] = {}
        for s in solutions:
            refs = s.get("entity_refs", "")
            if isinstance(refs, str):
                try:
                    refs = json.loads(refs)
                except Exception:
                    refs = []
            primary = (refs[0] if isinstance(refs[0], str) else str(refs[0])) if refs else "_general"
            by_entity.setdefault(primary, []).append(s)

        recs = []
        for entity, items in by_entity.items():
            if len(items) < self.SOLUTION_MIN_COUNT:
                continue
            # 取最新的解决方案内容
            latest = items[0]
            content = latest.get("content", "")
            snip = content[:120] if len(content) > 120 else content
            recs.append({
                "type": "recommendation",
                "entity": entity,
                "description": f"「{entity}」有 {len(items)} 条解决思路记录",
                "solution_count": len(items),
                "latest_solution": snip,
                "importance": latest.get("importance", 0.8),
                "source_memory_ids": [item["id"] for item in items],
                "rule": f"当用户讨论「{entity}」时，主动提醒已有 {len(items)} 条解决思路可供参考",
            })

        recs.sort(key=lambda r: -r["solution_count"])
        return recs[:5]
