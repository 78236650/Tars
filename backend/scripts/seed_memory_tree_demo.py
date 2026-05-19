#!/usr/bin/env python3
"""Seed demo memories + relations for memory entity tree / graph UI testing.

Usage (from backend/):
  python scripts/seed_memory_tree_demo.py
  python scripts/seed_memory_tree_demo.py --tenant default --wipe-tag
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tars.database import Database
from tars.memory.entity_id import compute_entity_id

TZ = timezone(timedelta(hours=8))
MARKER = "[TREE_DEMO_v42]"


def _now(offset_days: int = 0) -> str:
    return (datetime.now(TZ) - timedelta(days=offset_days)).isoformat()


def _upsert_memory(db: Database, tenant_id: str, *, content: str, **fields) -> str:
    mem = db.add_memory(content=content, category=fields.get("category", "fact"), tenant_id=tenant_id)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE memories SET
            importance = ?,
            memory_type = ?,
            pinned = ?,
            entity_refs = ?,
            compressed_from = ?,
            created_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            fields.get("importance", 0.5),
            fields.get("memory_type", "episodic"),
            fields.get("pinned", 0),
            json.dumps(fields.get("entity_refs"), ensure_ascii=False) if fields.get("entity_refs") else None,
            json.dumps(fields.get("compressed_from"), ensure_ascii=False) if fields.get("compressed_from") else None,
            fields.get("created_at", _now()),
            fields.get("updated_at", _now()),
            mem.id,
        ),
    )
    conn.commit()
    return mem.id


def _wipe_demo(db: Database, tenant_id: str) -> int:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM memories WHERE tenant_id = ? AND content LIKE ?",
        (tenant_id, f"%{MARKER}%"),
    )
    n = cur.rowcount
    conn.commit()
    return n


def seed(tenant_id: str = "default", wipe: bool = False) -> None:
    db = Database()
    if wipe:
        removed = _wipe_demo(db, tenant_id)
        print(f"removed {removed} old demo memories")

  # Entities
    alice = compute_entity_id("person", "张明")
    bob = compute_entity_id("person", "李华")
    tars = compute_entity_id("person", "TARS助手")
    hermes = compute_entity_id("project", "Hermes Agent")
    port = compute_entity_id("project", "洋山智慧港口")
    rag = compute_entity_id("concept", "RAG检索增强")
    bi = compute_entity_id("concept", "BI指标口径")

    src_ids = []
    for i in range(3):
        mid = _upsert_memory(
            db,
            tenant_id,
            content=f"{MARKER} 洋山港口二期：泊位调度指标讨论片段 {i+1}",
            memory_type="episodic",
            importance=0.35,
            entity_refs=[alice, port],
            created_at=_now(2 + i),
        )
        src_ids.append(mid)

    compressed_id = _upsert_memory(
        db,
        tenant_id,
        content=f"{MARKER} 【压缩】洋山港口二期建设与调度指标综述",
        memory_type="compressed",
        importance=0.85,
        entity_refs=[port],
        compressed_from=src_ids + ["archived-missing-id"],
        created_at=_now(1),
    )

    demos = [
        (f"{MARKER} 张明负责 Hermes Agent 产品路线与迭代排期。", [alice, hermes], "longterm", 0.75, 30),
        (f"{MARKER} 李华参与 RAG 检索链路与向量库选型评审。", [bob, rag, hermes], "longterm", 0.7, 25),
        (f"{MARKER} TARS 助手在记忆树 Demo 中展示实体关系图谱。", [tars, alice], "episodic", 0.4, 3),
        (f"{MARKER} BI 指标「日吞吐量」口径：当日完成箱量 / 24h。", [bi, port], "longterm", 0.8, 20),
        (f"{MARKER} 用户偏好：记忆管理默认查看实体树而非列表。", [alice], "episodic", 0.45, 5),
        (f"{MARKER} Hermes 与港口项目共享多份需求文档（共现测试）。", [hermes, port], "episodic", 0.5, 4),
    ]
    for text, refs, mtype, imp, days in demos:
        _upsert_memory(
            db,
            tenant_id,
            content=text,
            entity_refs=refs,
            memory_type=mtype,
            importance=imp,
            created_at=_now(days),
        )

    conn = db._get_conn()
    cur = conn.cursor()
    edges = [
        (alice, hermes, "owns", 0.9),
        (bob, hermes, "contributes_to", 0.75),
        (tars, alice, "assists", 0.85),
        (port, bi, "measured_by", 0.7),
        (hermes, rag, "uses", 0.8),
        (alice, port, "stakeholder_of", 0.65),
    ]
    now = _now()
    for fr, to, pred, conf in edges:
        cur.execute(
            """
            INSERT OR REPLACE INTO relations(from_entity, to_entity, predicate, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (fr, to, pred, conf, now),
        )
    conn.commit()

    from tars.memory.tree_builder import EntityTreeBuilder

    b = EntityTreeBuilder(db, tenant_id=tenant_id)
    tree = b.build()
    graph = b.build_graph()
    print(f"tenant={tenant_id} marker={MARKER}")
    print(f"  tree: entities={tree['stats']['entity_count']} memories={tree['stats']['memory_count']} nodes={tree['stats']['tree_node_count']}")
    print(f"  graph: nodes={graph['stats']['node_count']} edges={graph['stats']['edge_count']}")
    print(f"  compressed demo id={compressed_id}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tenant", default="default")
    p.add_argument("--wipe-tag", action="store_true", help="Remove prior demo rows with marker")
    args = p.parse_args()
    seed(args.tenant, wipe=args.wipe_tag)


if __name__ == "__main__":
    main()
