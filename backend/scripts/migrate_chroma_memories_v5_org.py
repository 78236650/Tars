#!/usr/bin/env python3
"""Merge per-user Chroma memory collections into org-level ``memories_org_default``."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tars.org import ORG_ID  # noqa: E402

TARGET_COLLECTION = f"memories_{ORG_ID}"


def load_memory_scope_map(db_path: str) -> Dict[str, Dict[str, str]]:
    """Map memory id -> {scope, user_id} from SQLite."""
    if not Path(db_path).is_file():
        return {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, scope, user_id FROM memories")
    except sqlite3.OperationalError:
        conn.close()
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for memory_id, scope, user_id in cur.fetchall():
        result[memory_id] = {
            "scope": scope or "private",
            "user_id": user_id or "",
        }
    conn.close()
    return result


def _infer_metadata(
    doc_id: str,
    existing_meta: Optional[Dict[str, Any]],
    suffix: str,
    scope_map: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    meta = dict(existing_meta or {})
    if doc_id in scope_map:
        meta["scope"] = scope_map[doc_id]["scope"]
        meta["user_id"] = scope_map[doc_id]["user_id"]
        return meta
    meta.setdefault("scope", "private")
    if suffix and suffix not in (ORG_ID, "default"):
        meta.setdefault("user_id", suffix)
    else:
        meta.setdefault("user_id", "")
    return meta


def migrate_chroma(
    vectorstore_path: str,
    db_path: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required for Chroma migration") from exc

    client = chromadb.PersistentClient(path=vectorstore_path)
    scope_map = load_memory_scope_map(db_path)

    target = None
    existing_ids: Set[str] = set()
    if not dry_run:
        try:
            target = client.get_collection(name=TARGET_COLLECTION)
            existing_ids = set(target.get(include=[])["ids"])
        except Exception:
            target = client.create_collection(
                name=TARGET_COLLECTION,
                metadata={"org_id": ORG_ID, "collection_type": "memories"},
            )

    stats: Dict[str, Any] = {
        "target": TARGET_COLLECTION,
        "merged": 0,
        "skipped_existing": 0,
        "source_collections": [],
    }

    for coll in client.list_collections():
        name = coll.name
        if not name.startswith("memories_"):
            continue
        if name == TARGET_COLLECTION:
            continue

        suffix = name[len("memories_") :]
        source = client.get_collection(name=name)
        data = source.get(include=["documents", "metadatas", "embeddings"])

        stats["source_collections"].append(name)
        for i, doc_id in enumerate(data.get("ids") or []):
            if doc_id in existing_ids:
                stats["skipped_existing"] += 1
                continue

            meta = _infer_metadata(
                doc_id,
                data["metadatas"][i] if data.get("metadatas") else None,
                suffix,
                scope_map,
            )
            if dry_run:
                stats["merged"] += 1
                continue

            kwargs: Dict[str, Any] = {
                "ids": [doc_id],
                "documents": [data["documents"][i]],
                "metadatas": [meta],
            }
            embeddings = data.get("embeddings")
            if embeddings and embeddings[i] is not None:
                kwargs["embeddings"] = [embeddings[i]]
            target.add(**kwargs)
            existing_ids.add(doc_id)
            stats["merged"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge per-user Chroma memory collections into org-level pool",
    )
    parser.add_argument(
        "--vectorstore",
        default=str(ROOT / "backend" / "data" / "vectorstore"),
        help="Path to Chroma persist directory",
    )
    parser.add_argument(
        "--db",
        default=str(ROOT / "backend" / "data" / "tars.db"),
        help="Path to SQLite database (for scope/user_id lookup)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    args = parser.parse_args()

    stats = migrate_chroma(args.vectorstore, args.db, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "applied"
    sources = ", ".join(stats["source_collections"]) or "(none)"
    print(
        f"[migrate_chroma_memories_v5_org] {mode}: "
        f"merged={stats['merged']} skipped_existing={stats['skipped_existing']} "
        f"target={stats['target']} sources=[{sources}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
