"""后处理反思 LLM — v2.2 分流写入：Semantic + Episodic + Core"""
import json
import re
from typing import List, Dict, Any, Optional

from .core_memory import CoreMemoryManager, BLOCK_NAMES
from .archival import ArchivalManager
from .domain_schema import PORT_ENTITY_TYPE_HINT, PORT_RELATION_TYPE_HINT


REFLECTION_PROMPT = """你是记忆管理助手。基于本轮对话，判断需要做的记忆操作。

当前 core memory：
- persona: {persona}
- user_profile: {user_profile}
- project_context: {project_context}
- working_principles: {working_principles}

本轮对话（注意：{web_status}）：
User: {user_msg}
Assistant: {assistant_msg}

输出严格的 JSON 数组，每个元素是一个操作。不要任何额外文字。

操作类型：
- {{"op": "upsert_entity", "name": "名称", "type": "person|project|tech|concept|org|terminal|berth|crane|vessel|voyage|yard|cargo_owner|container", "aliases": ["别名"], "attributes": {{"key":"value"}}, "confidence": 0.8}}
- {{"op": "upsert_relation", "from_name": "A", "from_type": "person", "to_name": "B", "to_type": "project", "predicate": "works_on|uses|colleague_of|part_of|berth_of|crane_serves|voyage_of|berths_at|yard_of|cargo_of", "confidence": 0.7}}
- {{"op": "log_episode", "content": "事件描述（1-2句中文）", "event_time": "ISO8601或空", "entity_refs": [{{"name":"X","type":"person"}}], "importance": 0.7}}
- {{"op": "update_episode", "content": "更新后的完整描述", "key_text": "旧记忆中的关键词片段（用于定位）", "entity_refs": [{{"name":"X","type":"person"}}], "importance": 0.7}}
- {{"op": "log_solution", "problem": "问题一句话", "root_cause": "根因", "approach": "解决步骤（1-3步，用；分隔）", "key_insight": "最关键的1条认知", "entity_refs": [{{"name":"X","type":"project"}}], "importance": 0.8}}
- {{"op": "log_correction", "what_was_wrong": "之前哪里错了", "what_is_correct": "正确应该是什么", "category": "fact_error|misunderstanding|wrong_approach|outdated", "importance": 0.85}}
- {{"op": "log_procedure", "name": "操作名称（如\"部署TARS到内网\"）", "steps": ["步骤1", "步骤2"], "triggers": ["关键词1","关键词2"], "entity_refs": [{{"name":"X","type":"project"}}], "importance": 0.9}}
- {{"op": "update_core", "block": "persona|user_profile|project_context|working_principles", "action": "append|replace", "old": "旧文本", "new": "新文本"}}
- {{"op": "forget", "block": "...", "line_contains": "关键词"}}
- {{"op": "noop"}}

实体与关系分类：
- """ + PORT_ENTITY_TYPE_HINT + """
- """ + PORT_RELATION_TYPE_HINT + """

分流规则（严格遵循）：
- 人/项目/技术/概念首次出现 → upsert_entity
- A 和 B 有关系首次或变化 → upsert_relation
- 带时间/决策/关联实体的事件 → log_episode。entity_refs 优先但不强制，无关联时 importance 减半
- 对已有 episodic 的补充/修正/深入 → update_episode。key_text 必须是旧记忆中的原文关键词（5-15字），content 是更新后的完整版本
- 用户描述了一个问题的完整解决过程（有明确的问题、根因、解决方案）→ log_solution。problem/root_cause/approach/key_insight 各一句话，importance 设 0.8
- 用户明确纠正了 Agent 的错误（"不对""错了""应该是""改成"）→ log_correction。准确记录错在哪里、正确是什么，importance 设 0.85
- 用户描述了可复用的操作步骤/SOP（有明确的步骤序列和触发场景）→ log_procedure。name 是简短名称，steps 是1-5步列表，triggers 是触发该SOP的关键词
- 用户不变偏好/技术栈/协作准则 → update_core（project_context 仅允许 replace 替换为1-2行快照）
- 过期 core 行 / 过时内容 → forget
- 无明显新信息 → noop

质量规则：
- ❌ 不要 archive 一次性操作步骤（如"创建了 main.py"）
- ❌ 不要 archive 临时性回答
- ✅ log_episode 的 content 控制在 2 句话以内，用中文

只输出 JSON 数组。"""


class Reflector:
    """v2.2 反思器：分流写入 Semantic + Episodic + Core"""

    def __init__(
        self,
        provider,
        core: CoreMemoryManager,
        archival: ArchivalManager,
        db=None,
    ):
        self.provider = provider
        self.core = core
        self.archival = archival
        self.db = db
        from ..org import ORG_ID

        self.tenant_id = getattr(core, "tenant_id", ORG_ID)

    async def reflect(
        self,
        user_msg: str,
        assistant_msg: str,
        used_web: bool = False,
    ) -> List[Dict[str, Any]]:
        """异步反思入口；返回执行的 ops 列表"""
        if not self.provider:
            return []
        if not user_msg.strip() or not assistant_msg.strip():
            return []

        snapshot = self.core.get_all()
        prompt = REFLECTION_PROMPT.format(
            persona=snapshot.get("persona", "")[:300],
            user_profile=snapshot.get("user_profile", "")[:300],
            project_context=snapshot.get("project_context", "")[:300],
            working_principles=snapshot.get("working_principles", "")[:300],
            user_msg=user_msg[:1500],
            assistant_msg=assistant_msg[:1500],
            web_status="本轮使用了 web 搜索" if used_web else "本轮未使用 web 搜索",
        )

        # v5.0.5/A3: 三层降级 —— LLM 不可用时记忆仍写入,不丢反思机会。
        # 第一层:LLM 反思
        text = None
        try:
            from ..models import ChatMessage
            messages = [
                ChatMessage(role="system", content="你是记忆管理助手。只输出 JSON。"),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self.provider.chat(messages, stream=False, temperature=0.1)
            text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            print(f"[Reflector] LLM 调用失败: {e} —— 降级到启发式")

        ops = self._parse_ops(text) if text else []

        # 第二层:LLM 失败或未产出有效 ops 时,用启发式规则提取
        if not ops:
            ops = self._heuristic_ops(user_msg, assistant_msg)
            if ops:
                print(f"[Reflector] 启发式降级产出 {len(ops)} 个 op")

        applied = []
        for op in ops:
            try:
                if await self._apply_op(op):
                    applied.append(op)
            except Exception as e:
                print(f"[Reflector] op 应用失败 {op}: {e}")

        # 第三层:前两层都没写入任何东西时,做最小归档,确保对话不被完全遗忘
        if not applied:
            try:
                min_op = self._minimal_archive_op(user_msg, assistant_msg)
                if min_op and await self._apply_op(min_op):
                    applied.append(min_op)
                    print("[Reflector] 最小归档降级:已存 1 条 episode")
            except Exception as e:
                print(f"[Reflector] 最小归档失败: {e}")

        if applied:
            print(f"[Reflector] ops={len(ops)} applied={len(applied)}")

        # v2.2: 从 Semantic 派生 project_context
        self._derive_project_context()

        return applied

    def _heuristic_ops(self, user_msg: str, assistant_msg: str) -> List[Dict[str, Any]]:
        """第二层降级:无 LLM 时用启发式规则产出记忆 op(v5.0.5/A3)。

        保守策略 —— 只在对话看起来含可记忆信息(足够长/含决策类信号词)时
        产出一条 log_episode,避免噪声。"""
        try:
            u = (user_msg or "").strip()
            a = (assistant_msg or "").strip()
            if len(u) < 8 or len(a) < 8:
                return []
            signals = (
                "决定", "选择", "采用", "改为", "偏好", "喜欢", "记住",
                "以后", "规则", "约定", "方案", "用", "配置",
            )
            if not any(s in u or s in a for s in signals):
                return []
            content = f"用户: {u[:120]}; 回应要点: {a[:120]}"
            return [{
                "op": "log_episode",
                "content": content[:240],
                "event_time": "",
                "entity_refs": [],
                "importance": 0.3,  # 启发式置信低,重要性减半
            }]
        except Exception:
            return []

    def _minimal_archive_op(self, user_msg: str, assistant_msg: str) -> Optional[Dict[str, Any]]:
        """第三层降级:最小归档(v5.0.5/A3)。

        前两层都没写入时,把本轮对话压成一条低重要性 episode,保证不彻底丢失。"""
        u = (user_msg or "").strip()
        a = (assistant_msg or "").strip()
        if not u or not a:
            return None
        return {
            "op": "log_episode",
            "content": f"[未反思归档] 用户: {u[:120]}; 回应: {a[:120]}"[:240],
            "event_time": "",
            "entity_refs": [],
            "importance": 0.2,
        }

    def _derive_project_context(self):
        """从 entities/relations/decisions 派生 project_context 快照"""
        if not self.db:
            return
        try:
            conn = self.db._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT name, attributes FROM entities WHERE type='project' ORDER BY importance DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return
            project_name = row[0]
            attrs = json.loads(row[1] or "{}")
            phase = attrs.get("phase", "")
            cur.execute(
                "SELECT content FROM memories WHERE tenant_id = ? AND category='decision' ORDER BY event_time DESC LIMIT 1",
                (self.tenant_id,),
            )
            dec_row = cur.fetchone()
            current_task = dec_row[0][:40] if dec_row else ""
            snapshot = f"项目: {project_name}"
            if phase:
                snapshot += f" | 阶段: {phase}"
            if current_task:
                snapshot += f" | 当前任务: {current_task}"
            if len(snapshot) > 200:
                snapshot = snapshot[:200]
            self.core.set("project_context", snapshot)
        except Exception as e:
            print(f"[Reflector] project_context 派生失败: {e}")

    @staticmethod
    def _parse_ops(text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            pass
        m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if m:
            try: return json.loads(m.group(1)) if isinstance(json.loads(m.group(1)), list) else []
            except json.JSONDecodeError: pass
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try: return json.loads(m.group(0)) if isinstance(json.loads(m.group(0)), list) else []
            except json.JSONDecodeError: pass
        return []

    async def _apply_op(self, op: Dict[str, Any]) -> bool:
        kind = op.get("op")
        if kind == "noop":
            return False
        if kind == "forget":
            return self._apply_forget(op)
        if kind == "update_core":
            return self._apply_update_core(op)
        if kind == "archive":
            return await self._apply_archive(op)
        if kind == "upsert_entity":
            return self._apply_upsert_entity(op)
        if kind == "upsert_relation":
            return self._apply_upsert_relation(op)
        if kind == "log_episode":
            return await self._apply_log_episode(op)
        if kind == "update_episode":
            return await self._apply_update_episode(op)
        if kind == "log_solution":
            return await self._apply_log_solution(op)
        if kind == "log_procedure":
            return await self._apply_log_procedure(op)
        if kind == "log_correction":
            return await self._apply_log_correction(op)
        return False

    def _apply_forget(self, op: dict) -> bool:
        block = op.get("block", "")
        line_contains = op.get("line_contains", "").strip()
        if block not in BLOCK_NAMES or not line_contains:
            return False
        return self.core.db.forget_core_line(block, line_contains, tenant_id=self.tenant_id)

    def _apply_update_core(self, op: dict) -> bool:
        block = op.get("block", "")
        if block not in BLOCK_NAMES:
            return False
        action = op.get("action", "append")
        new = op.get("new", "").strip()
        if not new:
            return False
        if action == "replace":
            old = op.get("old", "")
            return self.core.replace(block, old, new)
        return self.core.append(block, new)

    async def _apply_archive(self, op: dict) -> bool:
        content = op.get("content", "").strip()
        if not content:
            return False
        mem = await self.archival.insert(
            content=content,
            category=op.get("category", "fact"),
            importance=float(op.get("importance", 0.5)),
            source=op.get("source", "conversation"),
        )
        return mem is not None

    # ---- v2.2 新 ops ----

    def _apply_upsert_entity(self, op: dict) -> bool:
        if not self.db:
            return False
        from tars.memory.entity_id import compute_entity_id, normalize_entity_name
        name = op.get("name", "").strip()
        etype = op.get("type", "concept")
        if not name:
            return False
        eid = compute_entity_id(etype, name)
        aliases = list(set(op.get("aliases", []) + [name]))
        attrs = json.dumps(op.get("attributes", {}), ensure_ascii=False)
        conf = float(op.get("confidence", 0.5))
        import datetime
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone(timedelta(hours=8))).isoformat()

        conn = self.db._get_conn()
        cur = conn.cursor()

        # 1. 哈希 ID 直接命中？
        cur.execute("SELECT id, name, aliases, attributes, attributes_history, importance FROM entities WHERE id = ?", (eid,))
        row = cur.fetchone()

        # 2. 未命中 → FTS5 aliases 搜索
        merged_into = None
        if not row:
            alias_text = " ".join(aliases)
            try:
                cur.execute(
                    "SELECT e.id, e.name, e.aliases, e.attributes, e.attributes_history, e.importance FROM entities e JOIN entities_aliases_fts f ON e.rowid = f.rowid WHERE entities_aliases_fts MATCH ? LIMIT 1",
                    (alias_text.replace(" ", " OR "),))
                row2 = cur.fetchone()
                if row2:
                    merged_into = row2[0]
                    row = row2
                    print(f"[AliasMerge] {name} -> {row2[0]} ({row2[1]}) via FTS5")
            except Exception:
                pass

        # 3. FTS5 未命中 → 语义相似度搜索
        if not row:
            try:
                from tars.memory.deduplicator import jaccard_similarity
                cur.execute("SELECT id, name, aliases, attributes, attributes_history, importance FROM entities WHERE type=?", (etype,))
                all_entities = cur.fetchall()
                best_sim = 0.6  # 阈值
                best_row = None
                for erow in all_entities:
                    sim = jaccard_similarity(name.lower(), erow[1].lower())
                    if sim > best_sim:
                        best_sim = sim
                        best_row = erow
                if best_row:
                    merged_into = best_row[0]
                    row = best_row
                    print(f"[AliasMerge] {name} -> {best_row[0]} ({best_row[1]}) via semantic sim={best_sim:.2f}")
            except Exception:
                pass

        if row:
            old_name = row[1]
            old_aliases = json.loads(row[2] or "[]")
            old_attrs = json.loads(row[3] or "{}")
            history = json.loads(row[4] or "[]")
            new_aliases = list(set(old_aliases + aliases))
            new_attrs = {**old_attrs, **json.loads(attrs)}
            for k, v in json.loads(attrs).items():
                if k in old_attrs and old_attrs[k] != v:
                    history.append({"attr": k, "old": old_attrs[k], "new": v, "ts": now})
            new_imp = max(float(row[5] or 0.5), conf)
            target_id = row[0]
            cur.execute(
                "UPDATE entities SET name=?, aliases=?, attributes=?, attributes_history=?, importance=?, last_accessed=? WHERE id=?",
                (old_name, json.dumps(new_aliases, ensure_ascii=False),
                 json.dumps(new_attrs, ensure_ascii=False),
                 json.dumps(history, ensure_ascii=False), new_imp, now, target_id),
            )
        else:
            target_id = eid
            cur.execute(
                "INSERT INTO entities(id,type,name,aliases,attributes,attributes_history,importance,last_accessed,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (target_id, etype, name, json.dumps(aliases, ensure_ascii=False),
                 attrs, "[]", conf, now, now),
            )
            # 同步 FTS5
            try:
                cur.execute("INSERT INTO entities_aliases_fts(rowid, aliases) VALUES(last_insert_rowid(), ?)",
                           (json.dumps(aliases, ensure_ascii=False),))
            except Exception:
                pass

        conn.commit()
        return True
    def _apply_upsert_relation(self, op: dict) -> bool:
        if not self.db:
            return False
        from tars.memory.entity_id import compute_entity_id
        from_id = compute_entity_id(op.get("from_type", "concept"), op.get("from_name", ""))
        to_id = compute_entity_id(op.get("to_type", "concept"), op.get("to_name", ""))
        pred = op.get("predicate", "").strip()
        conf = float(op.get("confidence", 0.5))
        if not pred:
            return False
        import datetime
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone(timedelta(hours=8))).isoformat()

        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO relations(tenant_id,from_entity,to_entity,predicate,confidence,created_at) VALUES(?,?,?,?,?,?)",
            (self.tenant_id, from_id, to_id, pred, conf, now),
        )
        conn.commit()
        return True
    async def _apply_log_episode(self, op: dict) -> bool:
        content = op.get("content", "").strip()
        if not content:
            return False
        # v1.2: 优先 entity_refs_by_name（LLM 给 name+type，后端算 ID）
        entity_refs_raw = op.get("entity_refs_by_name") or op.get("entity_refs", [])
        importance = float(op.get("importance", 0.5))
        category = op.get("category", "fact")

        etype = op.get("type")
        if not entity_refs_raw and etype:
            # 兜底：concept 或 decision 类型
            category = "domain_knowledge" if etype == "concept" else "decision"
            entity_refs_raw = [{"name": content[:30], "type": etype}]

        if not entity_refs_raw:
            return False  # v1.2 硬约束：必须有 entity_refs

        from tars.memory.entity_id import compute_entity_id
        refs_with_ids = []
        for e in entity_refs_raw:
            if isinstance(e, dict):
                eid = compute_entity_id(e.get("type", "concept"), e.get("name", ""))
                refs_with_ids.append(eid)
        entity_refs = refs_with_ids

        event_time = op.get("event_time") or None

        # ── v5.0.5/A3: 写入前去重 ──
        # 在 entity 范围内检查是否与已有 episodic 重复或可更新，
        # 避免碎片堆积，减少对 Compressor 的依赖。
        if entity_refs and self.archival and self.archival.deduplicator:
            try:
                existing = self.db.get_recent_memories_for_entity(
                    entity_refs, limit=10, tenant_id=self.tenant_id
                )
                if existing:
                    is_dup, update_target = self.archival.deduplicator.is_duplicate(content, existing)
                    if is_dup and not update_target:
                        return False  # 完全重复，跳过
                    if is_dup and update_target:
                        self.db.update_memory(
                            update_target.id,
                            content=content,
                            importance=max(importance, getattr(update_target, "importance", 0) or 0),
                            category=category,
                            entity_refs=entity_refs,
                            event_time=event_time,
                            tenant_id=self.tenant_id,
                        )
                        return True
            except Exception as e:
                # 去重失败不影响正常写入
                print(f"[Reflector] 写入前去重失败，继续正常写入: {e}")

        import datetime
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone(timedelta(hours=8)))

        conn = self.db._get_conn()
        cur = conn.cursor()
        import uuid
        mid = str(uuid.uuid4())
        et = event_time or now.isoformat()
        refs_json = json.dumps(entity_refs, ensure_ascii=False) if entity_refs else None
        from tars.org import ORG_ID
        from tars.context import get_current_user_id

        try:
            writer_user_id = get_current_user_id()
        except RuntimeError:
            writer_user_id = None
        cur.execute(
            """
            INSERT INTO memories(id,tenant_id,user_id,content,category,importance,created_at,updated_at,last_accessed,access_count,source,event_time,entity_refs)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (mid, ORG_ID, writer_user_id, content, category, importance, now, now, None, 0, "conversation", et, refs_json),
        )
        try:
            cur.execute("INSERT INTO memories_fts(rowid,content,category) VALUES(last_insert_rowid(),?,?)", (content, category))
        except Exception:
            pass
        conn.commit()
        return True

    async def _apply_update_episode(self, op: dict) -> bool:
        """增量更新已有 episodic 记忆。

        LLM 判断本轮是对已有记忆的补充/修正时使用。key_text 用于在 entity
        范围内定位目标记忆；若未找到匹配，自动退化为 log_episode。
        """
        content = op.get("content", "").strip()
        key_text = op.get("key_text", "").strip()
        entity_refs_raw = op.get("entity_refs_by_name") or op.get("entity_refs", [])
        importance = float(op.get("importance", 0.5))

        if not content or not entity_refs_raw:
            return await self._apply_log_episode(op)

        from tars.memory.entity_id import compute_entity_id

        entity_ids = []
        for e in entity_refs_raw:
            if isinstance(e, dict):
                eid = compute_entity_id(e.get("type", "concept"), e.get("name", ""))
                entity_ids.append(eid)

        if not entity_ids:
            return await self._apply_log_episode(op)

        try:
            existing = self.db.get_recent_memories_for_entity(
                entity_ids, limit=15, tenant_id=self.tenant_id
            )
        except Exception:
            return await self._apply_log_episode(op)

        # 用 key_text 在已有记忆中搜索匹配
        target = None
        if key_text and existing:
            for mem in existing:
                if key_text in (mem.content or ""):
                    target = mem
                    break

        if not target:
            # key_text 未命中或为空，退化为新 log_episode
            return await self._apply_log_episode(op)

        # 找到匹配，更新已有记忆
        try:
            self.db.update_memory(
                target.id,
                content=content,
                importance=max(importance, getattr(target, "importance", 0) or 0),
                entity_refs=entity_ids,
                tenant_id=self.tenant_id,
            )
            return True
        except Exception:
            return await self._apply_log_episode(op)

    async def _apply_log_solution(self, op: dict) -> bool:
        """结构化记录解决思路。

        从对话中提取问题→根因→方案→关键认知的结构化模式，
        存入 memories 表作为 procedural memory，importance 默认 0.8。
        """
        problem = (op.get("problem") or "").strip()
        root_cause = (op.get("root_cause") or "").strip()
        approach = (op.get("approach") or "").strip()
        key_insight = (op.get("key_insight") or "").strip()

        if not problem:
            return False

        # 组装结构化内容
        parts = [f"问题：{problem}"]
        if root_cause:
            parts.append(f"根因：{root_cause}")
        if approach:
            parts.append(f"方案：{approach}")
        if key_insight:
            parts.append(f"关键认知：{key_insight}")
        content = "\n".join(parts)
        importance = float(op.get("importance", 0.8))

        entity_refs_raw = op.get("entity_refs_by_name") or op.get("entity_refs", [])
        from tars.memory.entity_id import compute_entity_id

        entity_ids = []
        for e in entity_refs_raw:
            if isinstance(e, dict):
                eid = compute_entity_id(e.get("type", "project"), e.get("name", ""))
                entity_ids.append(eid)

        import datetime
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone(timedelta(hours=8)))
        event_time = op.get("event_time") or now.isoformat()

        conn = self.db._get_conn()
        cur = conn.cursor()
        import uuid
        mid = str(uuid.uuid4())
        refs_json = __import__("json").dumps(entity_ids, ensure_ascii=False) if entity_ids else None
        from tars.org import ORG_ID
        from tars.context import get_current_user_id

        try:
            writer_user_id = get_current_user_id()
        except RuntimeError:
            writer_user_id = None

        cur.execute(
            """
            INSERT INTO memories(id,tenant_id,user_id,content,category,importance,created_at,updated_at,last_accessed,access_count,source,event_time,entity_refs,memory_type)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (mid, ORG_ID, writer_user_id, content, "solution", importance, now, now, None, 0, "conversation", event_time, refs_json, "procedural"),
        )
        try:
            cur.execute("INSERT INTO memories_fts(rowid,content,category) VALUES(last_insert_rowid(),?,?)", (content, "solution"))
        except Exception:
            pass
        conn.commit()
        return True
    async def _apply_log_procedure(self, op: dict) -> bool:
        """结构化记录可复用的操作步骤/SOP。

        从对话中提取可复用的操作步骤序列，存入 procedural memory。
        importance 默认 0.9（最高优先级，几乎不衰减）。
        """
        name = (op.get("name") or "").strip()
        steps = op.get("steps") or []
        triggers = op.get("triggers") or []
        importance = float(op.get("importance", 0.9))

        if not name:
            return False

        # 组装结构化内容
        content = f"SOP：{name}\n步骤：\n"
        for idx, step in enumerate(steps, 1):
            content += f"  {idx}. {step}\n"
        if triggers:
            content += f"触发词：{', '.join(triggers)}"

        entity_refs_raw = op.get("entity_refs_by_name") or op.get("entity_refs", [])
        from tars.memory.entity_id import compute_entity_id

        entity_ids = []
        for e in entity_refs_raw:
            if isinstance(e, dict):
                eid = compute_entity_id(e.get("type", "project"), e.get("name", ""))
                entity_ids.append(eid)

        import datetime
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone(timedelta(hours=8)))

        conn = self.db._get_conn()
        cur = conn.cursor()
        import uuid
        mid = str(uuid.uuid4())
        refs_json = __import__("json").dumps(entity_ids, ensure_ascii=False) if entity_ids else None
        from tars.org import ORG_ID
        from tars.context import get_current_user_id

        try:
            writer_user_id = get_current_user_id()
        except RuntimeError:
            writer_user_id = None

        cur.execute(
            """
            INSERT INTO memories(id,tenant_id,user_id,content,category,importance,created_at,updated_at,last_accessed,access_count,source,event_time,entity_refs,memory_type)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (mid, ORG_ID, writer_user_id, content, "procedure", importance, now, now, None, 0, "conversation", None, refs_json, "procedural"),
        )
        try:
            cur.execute("INSERT INTO memories_fts(rowid,content,category) VALUES(last_insert_rowid(),?,?)", (content, "procedure"))
        except Exception:
            pass
        conn.commit()
        return True
    async def _apply_log_correction(self, op: dict) -> bool:
        """记录用户对 Agent 的纠正。

        当用户指出 Agent 的错误时，记录"错了什么→正确应该是什么"，
        importance 默认 0.85，供 Evolution 系统分析后自动调整行为。
        """
        what_was_wrong = (op.get("what_was_wrong") or "").strip()
        what_is_correct = (op.get("what_is_correct") or "").strip()
        corr_category = (op.get("category") or "fact_error").strip()
        importance = float(op.get("importance", 0.85))

        if not what_was_wrong:
            return False

        content = f"纠正：{what_was_wrong}\n正确：{what_is_correct or '（用户未说明正确做法）'}"
        entity_refs_raw = op.get("entity_refs_by_name") or op.get("entity_refs", [])
        from tars.memory.entity_id import compute_entity_id

        entity_ids = []
        for e in entity_refs_raw:
            if isinstance(e, dict):
                eid = compute_entity_id(e.get("type", "concept"), e.get("name", ""))
                entity_ids.append(eid)

        import datetime
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone(timedelta(hours=8)))

        conn = self.db._get_conn()
        cur = conn.cursor()
        import uuid
        mid = str(uuid.uuid4())
        refs_json = __import__("json").dumps(entity_ids, ensure_ascii=False) if entity_ids else None
        from tars.org import ORG_ID
        from tars.context import get_current_user_id

        try:
            writer_user_id = get_current_user_id()
        except RuntimeError:
            writer_user_id = None

        cur.execute(
            """
            INSERT INTO memories(id,tenant_id,user_id,content,category,importance,created_at,updated_at,last_accessed,access_count,source,event_time,entity_refs,memory_type)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (mid, ORG_ID, writer_user_id, content, "correction", importance, now, now, None, 0, "conversation", None, refs_json, "procedural"),
        )
        try:
            cur.execute("INSERT INTO memories_fts(rowid,content,category) VALUES(last_insert_rowid(),?,?)", (content, "correction"))
        except Exception:
            pass
        conn.commit()
        return True
