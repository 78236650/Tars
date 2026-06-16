"""TARS Memory - 休眠期记忆管理 Agent
实现类似 Letta 的 Sleep-time Agent 模式，利用空闲时间对长期记忆进行异步合并、冲突检测和去重。

v5.2.0: consolidate_duplicates/resolve_conflicts/decay_stale_memories 已实现。
"""
from typing import Any, Dict, List, Optional
import datetime
from datetime import timezone, timedelta

from tars.memory.embeddings import deserialize_vector
from tars.memory.deduplicator import cosine_similarity, jaccard_similarity


class MemorySleepAgent:
    """休眠期记忆管理代理"""

    def __init__(self, db=None, archival_manager=None, reflector=None):
        self.db = db
        self.archival_manager = archival_manager
        self.reflector = reflector

    async def run_consolidation(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """执行一轮完整的记忆整理"""
        stats = {
            "consolidated": 0,
            "conflicts_resolved": 0,
            "decayed": 0,
            "errors": 0,
        }

        if not self.db:
            stats["errors"] = 1
            print("[MemorySleepAgent] 无可用数据库连接，跳过本轮整理")
            return stats

        try:
            consolidated_count = await self.consolidate_duplicates(tenant_id, user_id)
            stats["consolidated"] = consolidated_count

            conflicts_count = await self.resolve_conflicts(tenant_id, user_id)
            stats["conflicts_resolved"] = conflicts_count

            decayed_count = await self.decay_stale_memories(tenant_id, user_id)
            stats["decayed"] = decayed_count

        except Exception as e:
            stats["errors"] += 1
            import traceback
            print(f"[MemorySleepAgent] 整理失败: {e}")
            traceback.print_exc()

        return stats

    # ── v5.2.0: 去重与合并 ──

    async def consolidate_duplicates(self, tenant_id: str, user_id: str) -> int:
        """检测并合并高度相似的重复记忆。

        策略:
        1. 拉取最近更新的记忆 (top 50)。
        2. 通过嵌入向量余弦相似度 + Jaccard 文本相似度检测语义重复对 (sim > 0.90)。
        3. 对每对重复记忆: 合并内容、保留较高 importance、删除低分者。
        """
        consolidated = 0
        try:
            recents = self.db.get_recent_memories(
                limit=50, tenant_id=tenant_id, user_id=user_id
            )
        except Exception:
            recents = []

        if len(recents) < 2:
            return 0

        # 获取所有记忆的嵌入向量
        try:
            all_emb = self.db.get_all_memories_with_embeddings(tenant_id=tenant_id)
        except Exception:
            all_emb = []

        emb_map: Dict[str, List[float]] = {}
        for mem, blob, *_ in all_emb:
            if blob:
                try:
                    vec = deserialize_vector(blob)
                    if vec:
                        emb_map[mem.id] = vec
                except Exception:
                    pass

        # 按 category 分组以减少跨类别误判
        by_cat: Dict[str, List] = {}
        for mem in recents:
            cat = getattr(mem, "category", "general") or "general"
            by_cat.setdefault(cat, []).append(mem)

        merged_pairs: set = set()
        for cat, cat_mems in by_cat.items():
            for i in range(len(cat_mems)):
                a = cat_mems[i]
                if a.id in merged_pairs:
                    continue
                a_vec = emb_map.get(a.id)
                for j in range(i + 1, len(cat_mems)):
                    b = cat_mems[j]
                    if b.id in merged_pairs:
                        continue
                    b_vec = emb_map.get(b.id)

                    # 计算相似度
                    if a_vec and b_vec:
                        sim = cosine_similarity(a_vec, b_vec)
                    else:
                        sim = jaccard_similarity(
                            getattr(a, "content", ""), getattr(b, "content", "")
                        )

                    if sim < 0.90:
                        continue

                    a_imp = getattr(a, "importance", 0.5) or 0.5
                    b_imp = getattr(b, "importance", 0.5) or 0.5
                    if a_imp >= b_imp:
                        keeper, discard = a, b
                    else:
                        keeper, discard = b, a

                    # 合并内容
                    merged = (
                        f"{getattr(keeper, 'content', '')}\n"
                        f"[已合并 {discard.id[:8]} "
                        f"@ {getattr(discard, 'created_at', '?')}]"
                    )[:4096]
                    try:
                        self.db.update_memory(
                            memory_id=keeper.id,
                            content=merged,
                            category=getattr(keeper, "category", None),
                            tenant_id=tenant_id,
                        )
                    except Exception:
                        pass
                    try:
                        self.db.delete_memory(discard.id, tenant_id=tenant_id)
                    except Exception:
                        pass
                    merged_pairs.add(keeper.id)
                    merged_pairs.add(discard.id)
                    consolidated += 1
                    print(
                        f"[MemorySleepAgent] 合并: {keeper.id[:8]}←{discard.id[:8]} "
                        f"sim={sim:.3f} cat={cat}"
                    )

        return consolidated

    # ── v5.2.0: 冲突检测与解决 ──

    async def resolve_conflicts(self, tenant_id: str, user_id: str) -> int:
        """解决同一 category 内互斥或过时的记忆冲突。

        策略:
        1. 遍历每个 category，拉取所有记忆。
        2. 通过 Jaccard bigram 相似度 (sim > 0.40) 找到同主题的不同版本。
        3. BFS 连通分量分组，同组内只保留 updated_at 最新的，其余标记 importance → 0.15。
        """
        resolved = 0
        categories = [
            "user_preference", "project_record", "important_decision",
            "general", "domain_knowledge", "task_log", "kb",
        ]
        import itertools

        for cat in categories:
            try:
                mems = self.db.get_memories_by_category(
                    cat, limit=50, tenant_id=tenant_id, user_id=user_id
                )
            except Exception:
                continue
            if len(mems) < 2:
                continue

            # 基于 Jaccard bigram 相似度 + 最长公共前缀构建冲突图
            edges: Dict[str, set] = {}
            for a, b in itertools.combinations(mems, 2):
                ca = getattr(a, "content", "")
                cb = getattr(b, "content", "")
                sim = jaccard_similarity(ca, cb)
                # 计算最长公共前缀（对中文主题匹配很有效）
                lcp = self._lcp(ca, cb)
                # 冲突条件: Jaccard > 0.20 或 公共前缀 > 6 个字符
                is_conflict = sim >= 0.20 or lcp >= 6
                if not is_conflict:
                    continue
                edges.setdefault(a.id, set()).add(b.id)
                edges.setdefault(b.id, set()).add(a.id)

            # BFS 连通分量 → 冲突组
            visited: set = set()
            for mem in mems:
                if mem.id in visited or mem.id not in edges:
                    continue
                group_ids = []
                stack = [mem.id]
                while stack:
                    mid = stack.pop()
                    if mid in visited:
                        continue
                    visited.add(mid)
                    group_ids.append(mid)
                    for neighbor in edges.get(mid, set()):
                        if neighbor not in visited:
                            stack.append(neighbor)

                if len(group_ids) < 2:
                    continue
                group_mems = [m for m in mems if m.id in group_ids]
                group_mems.sort(
                    key=lambda m: (
                        getattr(m, "updated_at", None)
                        or getattr(m, "created_at", None)
                        or datetime.datetime(2000, 1, 1)
                    ),
                    reverse=True,
                )
                keeper = group_mems[0]
                for stale in group_mems[1:]:
                    try:
                        old = getattr(stale, "content", "")
                        new_c = (
                            f"{old}\n"
                            f"[superseded by {keeper.id[:8]} @ {keeper.updated_at}]"
                        )[:4096]
                        self.db.update_memory(
                            memory_id=stale.id,
                            content=new_c,
                            importance=0.15,
                            tenant_id=tenant_id,
                        )
                    except Exception as e:
                        print(f"[MemorySleepAgent] update_memory failed: {e}")
                    resolved += 1
                print(
                    f"[MemorySleepAgent] 冲突解决: cat={cat} "
                    f"group_size={len(group_mems)} keeper={keeper.id[:8]}"
                )

        return resolved

    def _extract_topic_key(self, content: str) -> str:
        """保留兼容；实际冲突检测已迁移到 Jaccard bigram + LCP 方案。"""
        return ""

    @staticmethod
    def _lcp(a: str, b: str) -> int:
        """最长公共前缀长度（字符级）。"""
        n = min(len(a), len(b))
        for i in range(n):
            if a[i] != b[i]:
                return i
        return n

    # ── v5.2.0: 衰减与清理 ──

    async def decay_stale_memories(self, tenant_id: str, user_id: str) -> int:
        """对长期未访问的记忆执行加速衰减和清理。

        策略:
        1. decay_importance(): 对所有超 24h 未访问的 -0.01/天（全局操作）。
        2. cleanup_old_memories(): 删除 importance<0.15 且 >30 天未访问的（全局操作）。
        """
        try:
            decay_count = self.db.decay_importance()
            cleanup_count = self.db.cleanup_old_memories(
                min_importance=0.15, max_age_days=30
            )
            total = decay_count + cleanup_count
            if total > 0:
                print(
                    f"[MemorySleepAgent] 衰减: decay={decay_count} cleanup={cleanup_count}"
                )
            return total
        except Exception as e:
            print(f"[MemorySleepAgent] 衰减失败: {e}")
            return 0
