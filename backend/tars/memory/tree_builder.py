"""Build entity-centric memory tree for the memory management UI."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .core_memory import BLOCK_NAMES, BLOCK_TITLES, CoreMemoryManager
from .entity_id import compute_entity_id

TYPE_ORDER = ["person", "project", "concept", "decision"]
TYPE_LABELS = {
    "person": "人物",
    "project": "项目",
    "concept": "概念",
    "decision": "决策",
}
BUCKET_ORDER = ["longterm", "recent", "compressed"]
BUCKET_LABELS = {
    "longterm": "长期记忆",
    "recent": "近期记忆",
    "compressed": "压缩记忆",
}

TZ = timezone(timedelta(hours=8))


def normalize_entity_ref(ref: Any) -> Tuple[str, str, str]:
    """Return (entity_id, entity_type, display_hint)."""
    if isinstance(ref, dict):
        etype = str(ref.get("type") or "concept").strip() or "concept"
        name = str(ref.get("name") or "").strip()
        eid = ref.get("id") or compute_entity_id(etype, name)
        return str(eid), etype, name or str(eid)
    text = str(ref).strip()
    if not text:
        return "", "concept", ""
    if ":" in text:
        etype = text.split(":", 1)[0] or "concept"
        return text, etype, text
    eid = compute_entity_id("concept", text)
    return eid, "concept", text


def primary_entity_id(entity_refs: Optional[List[Any]]) -> Optional[str]:
    if not entity_refs:
        return None
    eid, _, _ = normalize_entity_ref(entity_refs[0])
    return eid or None


def co_entity_ids(entity_refs: Optional[List[Any]]) -> List[str]:
    if not entity_refs or len(entity_refs) < 2:
        return []
    out: List[str] = []
    for ref in entity_refs[1:]:
        eid, _, _ = normalize_entity_ref(ref)
        if eid and eid not in out:
            out.append(eid)
    return out


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=TZ)
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=TZ)
    except ValueError:
        return None


def _is_recent_episodic(memory) -> bool:
    if (memory.memory_type or "episodic") != "episodic":
        return False
    created = _parse_dt(memory.created_at)
    if not created:
        return True
    return created >= datetime.now(TZ) - timedelta(days=7)


def classify_bucket(memory) -> Optional[str]:
    mtype = memory.memory_type or "episodic"
    if mtype == "compressed":
        return "compressed"
    if mtype == "longterm" or (memory.importance or 0) >= 0.6 or memory.pinned:
        return "longterm"
    if _is_recent_episodic(memory):
        return "recent"
    return None


def _memory_leaf(memory, co_entities: List[str]) -> Dict[str, Any]:
    content = memory.content or ""
    return {
        "id": memory.id,
        "kind": "memory",
        "label": (content[:80] + "…") if len(content) > 80 else content,
        "meta": {
            "memory_type": memory.memory_type or "episodic",
            "importance": memory.importance or 0.5,
            "pinned": bool(memory.pinned),
            "category": memory.category,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
            "compressed_from": memory.compressed_from or [],
            "co_entities": co_entities,
        },
        "children": [],
    }


class EntityTreeBuilder:
    def __init__(self, db, tenant_id: str = "default", max_per_bucket: int = 30):
        self.db = db
        self.tenant_id = tenant_id
        self.max_per_bucket = max(1, max_per_bucket)

    @staticmethod
    def _count_tree_nodes(nodes: List[Dict[str, Any]]) -> int:
        total = 0

        def walk(items: List[Dict[str, Any]]) -> None:
            nonlocal total
            for node in items:
                total += 1
                walk(node.get("children") or [])

        walk(nodes)
        return total

    def build(self, *, include_core: bool = True, include_orphan: bool = True) -> Dict[str, Any]:
        memories = self.db.list_memories_for_tree(tenant_id=self.tenant_id)
        entity_labels = self._load_entity_labels(memories)
        registered = set(entity_labels.keys())

        by_entity: Dict[str, List[Any]] = defaultdict(list)
        orphans: List[Any] = []

        for memory in memories:
            eid = primary_entity_id(memory.entity_refs)
            if eid:
                by_entity[eid].append(memory)
            else:
                orphans.append(memory)

        entity_meta: Dict[str, Dict[str, Any]] = {}
        for eid, mems in by_entity.items():
            etype = eid.split(":", 1)[0] if ":" in eid else "concept"
            entity_meta[eid] = {
                "type": etype,
                "label": entity_labels.get(eid) or self._fallback_label(eid, mems),
                "is_ghost": eid not in registered,
                "memories": mems,
            }

        nodes: List[Dict[str, Any]] = []
        if include_core:
            nodes.append(self._build_core_branch())

        type_groups: Dict[str, List[str]] = defaultdict(list)
        for eid, meta in entity_meta.items():
            etype = meta["type"]
            if etype not in TYPE_ORDER:
                etype = "other"
            type_groups[etype].append(eid)

        for etype in [*TYPE_ORDER, "other"]:
            eids = type_groups.get(etype, [])
            if not eids:
                continue
            eids.sort(
                key=lambda x: (
                    -self._entity_max_importance(entity_meta[x]["memories"]),
                    -len(entity_meta[x]["memories"]),
                    entity_meta[x]["label"],
                )
            )
            nodes.append(
                self._type_group_node(etype, [self._entity_node(eid, entity_meta[eid]) for eid in eids])
            )

        if include_orphan and orphans:
            nodes.append(self._orphan_node(orphans))

        ghost_count = sum(1 for m in entity_meta.values() if m["is_ghost"])
        relation_count = self._count_relations()

        return {
            "view": "entity",
            "tenant_id": self.tenant_id,
            "stats": {
                "entity_count": len(entity_meta),
                "memory_count": len(memories),
                "orphan_count": len(orphans),
                "ghost_entity_count": ghost_count,
                "relation_count": relation_count,
                "core_filled_blocks": self._core_filled_count(),
                "compressed_count": sum(1 for m in memories if (m.memory_type or "") == "compressed"),
                "tree_node_count": self._count_tree_nodes(nodes),
            },
            "nodes": nodes,
        }

    def build_provenance(self) -> Dict[str, Any]:
        memories = self.db.list_memories_for_tree(tenant_id=self.tenant_id)
        memory_by_id = {m.id: m for m in memories}
        compressed = [m for m in memories if (m.memory_type or "") == "compressed"]
        compressed.sort(
            key=lambda m: _parse_dt(m.updated_at or m.created_at) or datetime.min.replace(tzinfo=TZ),
            reverse=True,
        )

        archived_count = 0
        source_count = 0
        children_nodes: List[Dict[str, Any]] = []

        for comp in compressed:
            sources: List[Dict[str, Any]] = []
            for src_id in comp.compressed_from or []:
                source_count += 1
                src = memory_by_id.get(src_id)
                if src:
                    sources.append(_memory_leaf(src, co_entity_ids(src.entity_refs)))
                else:
                    archived_count += 1
                    short = src_id[:8] + "…" if len(src_id) > 8 else src_id
                    sources.append(
                        {
                            "id": f"archived:{src_id}",
                            "kind": "archived",
                            "label": f"已归档 ({short})",
                            "meta": {"source_id": src_id, "archived": True},
                            "children": [],
                        }
                    )
            content = comp.content or ""
            children_nodes.append(
                {
                    "id": comp.id,
                    "kind": "compressed",
                    "label": (content[:80] + "…") if len(content) > 80 else content,
                    "meta": {
                        "memory_type": "compressed",
                        "importance": comp.importance or 0.5,
                        "source_count": len(comp.compressed_from or []),
                        "compressed_from": comp.compressed_from or [],
                        "created_at": comp.created_at.isoformat() if comp.created_at else None,
                    },
                    "children": sources,
                }
            )

        nodes: List[Dict[str, Any]] = []
        if children_nodes:
            nodes.append(
                {
                    "id": "__provenance__",
                    "kind": "system",
                    "label": "压缩谱系",
                    "meta": {"compressed_count": len(compressed)},
                    "children": children_nodes,
                }
            )

        return {
            "view": "provenance",
            "tenant_id": self.tenant_id,
            "stats": {
                "compressed_count": len(compressed),
                "source_count": source_count,
                "archived_count": archived_count,
                "memory_count": len(memories),
                "entity_count": 0,
                "orphan_count": 0,
                "ghost_entity_count": 0,
                "relation_count": self._count_relations(),
                "core_filled_blocks": 0,
                "tree_node_count": self._count_tree_nodes(nodes),
            },
            "nodes": nodes,
        }

    def get_relations(self, entity_id: str) -> Dict[str, Any]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT from_entity, to_entity, predicate, confidence, created_at
            FROM relations
            WHERE from_entity = ? OR to_entity = ?
            ORDER BY confidence DESC, created_at DESC
            """,
            (entity_id, entity_id),
        )
        rows = cur.fetchall()
        labels = self._load_entity_labels_by_ids(
            {r[0] for r in rows} | {r[1] for r in rows}
        )
        outgoing, incoming = [], []
        for from_e, to_e, pred, conf, _created in rows:
            edge = {
                "peer_entity": to_e if from_e == entity_id else from_e,
                "peer_label": labels.get(to_e if from_e == entity_id else from_e, from_e),
                "predicate": pred,
                "confidence": conf,
                "direction": "outgoing" if from_e == entity_id else "incoming",
            }
            if from_e == entity_id:
                outgoing.append(edge)
            else:
                incoming.append(edge)
        return {
            "entity_id": entity_id,
            "entity_label": labels.get(entity_id, entity_id),
            "outgoing": outgoing,
            "incoming": incoming,
        }

    def _build_core_branch(self) -> Dict[str, Any]:
        core = CoreMemoryManager(self.db, tenant_id=self.tenant_id)
        blocks = core.get_all()
        children = []
        filled = 0
        for name in BLOCK_NAMES:
            content = (blocks.get(name) or "").strip()
            if content:
                filled += 1
            children.append(
                {
                    "id": f"core:{name}",
                    "kind": "core_block",
                    "label": BLOCK_TITLES.get(name, name),
                    "meta": {
                        "block": name,
                        "char_count": len(content),
                        "line_count": len(content.splitlines()) if content else 0,
                        "filled": bool(content),
                    },
                    "children": [],
                }
            )
        return {
            "id": "__core__",
            "kind": "system",
            "label": "核心记忆",
            "meta": {"filled_blocks": filled, "total_blocks": len(BLOCK_NAMES)},
            "children": children,
        }

    def _type_group_node(self, etype: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "id": f"__type:{etype}",
            "kind": "type_group",
            "label": TYPE_LABELS.get(etype, "其他"),
            "meta": {"entity_type": etype, "entity_count": len(children)},
            "children": children,
        }

    def _entity_node(self, eid: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        mems = meta["memories"]
        buckets: Dict[str, List[Any]] = defaultdict(list)
        for memory in mems:
            bucket = classify_bucket(memory)
            if bucket:
                buckets[bucket].append(memory)

        bucket_nodes = []
        counts = {"longterm": 0, "recent": 0, "compressed": 0}
        for bucket in BUCKET_ORDER:
            items = buckets.get(bucket, [])
            if not items:
                continue
            counts[bucket] = len(items)
            items.sort(
                key=lambda m: (
                    not bool(m.pinned),
                    -(m.importance or 0),
                    _parse_dt(m.event_time or m.created_at) or datetime.min.replace(tzinfo=TZ),
                ),
                reverse=True,
            )
            truncated = len(items) > self.max_per_bucket
            visible = items[: self.max_per_bucket]
            children = [
                _memory_leaf(m, co_entity_ids(m.entity_refs))
                for m in visible
            ]
            if truncated:
                children.append(
                    {
                        "id": f"{eid}:bucket:{bucket}:more",
                        "kind": "more",
                        "label": f"还有 {len(items) - self.max_per_bucket} 条",
                        "meta": {"bucket": bucket, "total": len(items), "truncated": True},
                        "children": [],
                    }
                )
            bucket_nodes.append(
                {
                    "id": f"{eid}:bucket:{bucket}",
                    "kind": "bucket",
                    "label": BUCKET_LABELS[bucket],
                    "meta": {"count": len(items), "truncated": truncated, "bucket": bucket},
                    "children": children,
                }
            )

        return {
            "id": eid,
            "kind": "entity",
            "label": meta["label"],
            "meta": {
                "type": meta["type"],
                "memory_count": len(mems),
                "longterm_count": counts["longterm"],
                "recent_count": counts["recent"],
                "compressed_count": counts["compressed"],
                "max_importance": self._entity_max_importance(mems),
                "is_ghost": meta["is_ghost"],
            },
            "children": bucket_nodes,
        }

    def _orphan_node(self, orphans: List[Any]) -> Dict[str, Any]:
        orphans.sort(key=lambda m: -(m.importance or 0))
        truncated = len(orphans) > self.max_per_bucket
        visible = orphans[: self.max_per_bucket]
        children = [_memory_leaf(m, []) for m in visible]
        if truncated:
            children.append(
                {
                    "id": "__orphan__:more",
                    "kind": "more",
                    "label": f"还有 {len(orphans) - self.max_per_bucket} 条",
                    "meta": {"truncated": True, "total": len(orphans)},
                    "children": [],
                }
            )
        return {
            "id": "__orphan__",
            "kind": "system",
            "label": "未归类",
            "meta": {"memory_count": len(orphans), "truncated": truncated},
            "children": children,
        }

    def _load_entity_labels(self, memories: List[Any]) -> Dict[str, str]:
        ids: set = set()
        for memory in memories:
            for ref in memory.entity_refs or []:
                eid, _, hint = normalize_entity_ref(ref)
                if eid:
                    ids.add(eid)
        return self._load_entity_labels_by_ids(ids)

    def _load_entity_labels_by_ids(self, entity_ids: set) -> Dict[str, str]:
        if not entity_ids:
            return {}
        conn = self.db._get_conn()
        cur = conn.cursor()
        placeholders = ",".join("?" * len(entity_ids))
        cur.execute(
            f"SELECT id, name FROM entities WHERE id IN ({placeholders})",
            list(entity_ids),
        )
        labels = {row[0]: row[1] for row in cur.fetchall()}
        for eid in entity_ids:
            labels.setdefault(eid, eid)
        return labels

    @staticmethod
    def _fallback_label(eid: str, memories: List[Any]) -> str:
        for memory in memories:
            for ref in memory.entity_refs or []:
                rid, _, hint = normalize_entity_ref(ref)
                if rid == eid and hint and hint != eid:
                    return hint
        if ":" in eid:
            return eid.split(":", 1)[0] + " · " + eid.split(":", 1)[1][:8]
        return eid

    @staticmethod
    def _entity_max_importance(memories: List[Any]) -> float:
        if not memories:
            return 0.0
        return max((m.importance or 0) for m in memories)

    def _core_filled_count(self) -> int:
        core = CoreMemoryManager(self.db, tenant_id=self.tenant_id)
        return sum(1 for name in BLOCK_NAMES if (core.get(name) or "").strip())

    def build_graph(self, max_edges: int = 800) -> Dict[str, Any]:
        """Tenant-scoped entity relation graph for force-directed UI."""
        memories = self.db.list_memories_for_tree(self.tenant_id, limit=5000)
        entity_index: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"memory_count": 0, "type": "concept", "label": ""}
        )

        for memory in memories:
            refs = memory.entity_refs or []
            for ref in refs:
                eid, etype, hint = normalize_entity_ref(ref)
                if not eid:
                    continue
                row = entity_index[eid]
                row["type"] = etype
                if hint and hint != eid:
                    row["label"] = hint
            pid = primary_entity_id(refs)
            if pid and pid in entity_index:
                entity_index[pid]["memory_count"] += 1

        for eid in list(entity_index.keys()):
            if not entity_index[eid]["label"]:
                entity_index[eid]["label"] = self._fallback_label(eid, memories)

        entity_ids = set(entity_index.keys())
        if not entity_ids:
            return {
                "tenant_id": self.tenant_id,
                "nodes": [],
                "edges": [],
                "stats": {"node_count": 0, "edge_count": 0, "truncated": False},
            }

        labels = self._load_entity_labels_by_ids(entity_ids)
        for eid, row in entity_index.items():
            if labels.get(eid):
                row["label"] = labels[eid]

        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT from_entity, to_entity, predicate, confidence
            FROM relations
            ORDER BY confidence DESC, created_at DESC
            """
        )
        edges: List[Dict[str, Any]] = []
        truncated = False
        for from_e, to_e, pred, conf in cur.fetchall():
            if from_e not in entity_ids or to_e not in entity_ids:
                continue
            if len(edges) >= max_edges:
                truncated = True
                break
            edges.append(
                {
                    "from": from_e,
                    "to": to_e,
                    "predicate": pred,
                    "confidence": conf,
                }
            )

        nodes = [
            {
                "id": eid,
                "label": row["label"] or eid,
                "type": row["type"],
                "memory_count": row["memory_count"],
            }
            for eid, row in sorted(entity_index.items(), key=lambda x: (-x[1]["memory_count"], x[0]))
        ]
        return {
            "tenant_id": self.tenant_id,
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "truncated": truncated,
            },
        }

    def search(self, query: str, limit: int = 20, view: str = "entity") -> Dict[str, Any]:
        q = query.strip().lower()
        if not q:
            return {"query": query, "view": view, "items": []}

        built = self.build_provenance() if view == "provenance" else self.build()
        items: List[Dict[str, Any]] = []
        seen: set = set()

        def walk(nodes: List[Dict[str, Any]], path: List[str]) -> None:
            if len(items) >= limit:
                return
            for node in nodes:
                nid = node["id"]
                path_next = path + [nid]
                haystack = f"{node.get('label', '')} {nid}".lower()
                if node.get("kind") == "memory":
                    meta = node.get("meta") or {}
                    haystack += f" {meta.get('category', '')}"
                if q in haystack and nid not in seen:
                    seen.add(nid)
                    items.append(
                        {
                            "node_id": nid,
                            "kind": node.get("kind"),
                            "label": node.get("label"),
                            "path": path_next,
                        }
                    )
                walk(node.get("children") or [], path_next)

        walk(built.get("nodes") or [], [])
        return {"query": query, "view": view, "items": items[:limit]}

    def _count_relations(self) -> int:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM relations")
        row = cur.fetchone()
        return int(row[0]) if row else 0
