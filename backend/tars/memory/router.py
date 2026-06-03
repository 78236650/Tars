"""MemoryRouter — v2.2 四路融合检索 + 兜底 HybridSearch"""
import json
from typing import List, Dict, Any, Optional

from tars.org import ORG_ID
from tars.memory.decay import decay_score, hours_since
from tars.memory.deduplicator import cosine_similarity
from tars.memory.embeddings import EmbeddingProvider, deserialize_vector
from tars.memory.search import HybridSearch
from tars.memory.entity_id import compute_entity_id


class MemoryRouter:
    """四路并行 + 融合打分 + 降级切换"""

    def __init__(self, db, embedding_provider: Optional[EmbeddingProvider] = None, tenant_id: str = ORG_ID):
        self.db = db
        self.ep = embedding_provider
        self.tenant_id = tenant_id
        self.hybrid = HybridSearch(db, embedding_provider, tenant_id=tenant_id)

    def for_tenant(self, tenant_id: str):
        return MemoryRouter(self.db, self.ep, tenant_id=tenant_id)

    def retrieve(self, user_msg: str, working_ctx: dict = None, limit: int = 6) -> Dict[str, Any]:
        """主入口：四路召回 + 融合。返回 dict 供 system prompt 拼装"""
        wc = working_ctx or {}
        scored: dict = {}

        try:
            # 1. 实体路 (0.4)
            self._entity_route(user_msg, wc, scored)
            # 2. 时间线路 (0.2)
            self._timeline_route(wc, scored)
            # 3. 向量路 (0.3)
            self._vector_route(user_msg, wc, scored)
            # 4. 关键词路 (0.1)
            self._keyword_route(user_msg, scored)
        except Exception as e:
            print(f"[MemoryRouter] 路由异常: {e}，降级 HybridSearch")
            return self._fallback(user_msg, limit)

        ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)[:limit]

        # 命中强化
        for mem_id, _ in ranked:
            try:
                self.db.reinforce_memory(mem_id)
            except Exception:
                pass

        # 构造注入结构
        return self._format_results(ranked, wc)

    # ---- 四路 ----

    def _entity_route(self, user_msg: str, wc: dict, scored: dict):
        focus = wc.get("focus_entities", []) or []
        entities_mentioned = []
        snapshot = wc.get("last_scene_snapshot", {})
        if snapshot:
            for e in snapshot.get("entities_mentioned", []):
                eid = compute_entity_id(e.get("type", "concept"), e.get("name", ""))
                entities_mentioned.append(eid)
        all_ids = list({*focus, *entities_mentioned})

        if not all_ids:
            return

        conn = self.db._get_conn()
        cur = conn.cursor()
        # 查实体属性
        entity_info = {}
        for eid in all_ids[:8]:
            cur.execute("SELECT id, type, name, attributes, importance FROM entities WHERE id=?", (eid,))
            row = cur.fetchone()
            if row:
                entity_info[eid] = {"id": row[0], "type": row[1], "name": row[2],
                                     "attrs": json.loads(row[3] or "{}"), "imp": row[4] or 0.5}
                scored[eid] = ({"type": "entity", "data": entity_info[eid]}, 0.4)

        # 查关联 episodic
        if entity_info:
            placeholders = ",".join(["?"] * len(entity_info))
            cur.execute(f"""
                SELECT id, content, category, importance, event_time
                FROM memories WHERE tenant_id = ? AND entity_refs IS NOT NULL
                AND ({" OR ".join([f"entity_refs LIKE ?" for _ in entity_info])})
                ORDER BY event_time DESC LIMIT 5
            """, [self.tenant_id, *[f"%{eid}%" for eid in entity_info]])
            for row in cur.fetchall():
                mid = f"ep_{row[0]}"
                imp = row[3] or 0.5
                scored[mid] = ({"type": "episode", "content": row[1], "category": row[2],
                                 "event_time": row[4]}, 0.35 + imp * 0.1)

    def _timeline_route(self, wc: dict, scored: dict):
        focus = wc.get("focus_entities", []) or []
        if not focus:
            return
        conn = self.db._get_conn()
        cur = conn.cursor()
        for eid in focus[:3]:
            cur.execute("""
                SELECT id, content, importance, event_time FROM memories
                WHERE tenant_id = ? AND entity_refs LIKE ? ORDER BY event_time DESC LIMIT 2
            """, (self.tenant_id, f"%{eid}%",))
            for row in cur.fetchall():
                mid = f"tl_{row[0]}"
                if mid not in scored:
                    imp = row[2] or 0.5
                    scored[mid] = ({"type": "timeline", "content": row[1], "event_time": row[3]}, 0.2 * imp)

    def _vector_route(self, user_msg: str, wc: dict, scored: dict):
        hints = wc.get("last_scene_snapshot", {}).get("recall_hints", [])
        query = user_msg
        if hints:
            query += " " + " ".join(hints)
        results = self.hybrid.search(query, limit=5)
        for mem in results:
            mid = f"vec_{mem.id}"
            if mid not in scored:
                scored[mid] = ({"type": "knowledge", "content": mem.content, "category": mem.category}, 0.3)

    def _keyword_route(self, user_msg: str, scored: dict):
        results = self.db.search_memories(user_msg, limit=3, tenant_id=self.tenant_id)
        for mem in results:
            mid = f"kw_{mem.id}"
            if mid not in scored:
                scored[mid] = ({"type": "knowledge", "content": mem.content, "category": mem.category}, 0.1)

    # ---- 兜底 ----

    def _fallback(self, user_msg: str, limit: int) -> Dict[str, Any]:
        results = self.hybrid.search(user_msg, limit=limit)
        items = [{"type": "knowledge", "content": m.content, "category": m.category} for m in results]
        return {"entities": [], "events": [], "knowledge": items}

    # ---- 格式化 ----

    def _format_results(self, ranked: list, wc: dict) -> Dict[str, Any]:
        entities = []
        events = []
        knowledge = []

        for item, score in ranked:
            t = item.get("type", "knowledge")
            if t == "entity":
                e = item["data"]
                attrs_str = ", ".join(f"{k}={v}" for k, v in e.get("attrs", {}).items())
                entities.append(f"[{e['name']}] {attrs_str}")
            elif t in ("episode", "timeline"):
                ts = (item.get("event_time") or "")[:10]
                events.append(f"({ts}) {item['content']}")
            else:
                knowledge.append(f"[{item.get('category', 'fact')}] {item['content']}")

        return {"entities": entities, "events": events, "knowledge": knowledge}

    def build_injection(self, ctx: Dict[str, Any]) -> str:
        """将检索结果转为 system prompt 注入文本"""
        parts = []
        if ctx.get("entities"):
            parts.append("### 涉及的实体\n" + "\n".join(f"- {e}" for e in ctx["entities"]))
        if ctx.get("events"):
            parts.append("### 最近相关事件\n" + "\n".join(f"- {e}" for e in ctx["events"]))
        if ctx.get("knowledge"):
            parts.append("### 相关知识\n" + "\n".join(f"- {k}" for k in ctx["knowledge"]))
        if not parts:
            return ""
        return "## 相关上下文\n\n" + "\n\n".join(parts)
