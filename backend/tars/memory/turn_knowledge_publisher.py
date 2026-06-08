"""将「记住要点」合成一篇知识库文档。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional


from ..org import ORG_ID


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def publish_synthesized_note(
    *,
    db,
    vector_store,
    embedding_provider,
    tenant_id: str = ORG_ID,
    title: str,
    markdown: str,
    source_memory_ids: Optional[List[str]] = None,
) -> Optional[str]:
    """写入合成笔记到 Wiki，返回 page_name。"""
    text = (markdown or "").strip()
    if not text or db is None:
        return None

    doc_title = title.strip() or f"对话精华({datetime.now().strftime('%Y-%m-%d')})"

    # 直接写入 Wiki
    try:
        import os as _os
        from pathlib import Path as _Path
        from tars.wiki.store import WikiStore

        wiki_dir = _Path(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__)))) / "data" / "wiki"
        store = WikiStore(wiki_dir=wiki_dir)
        page_name = f"memory-{uuid.uuid4().hex[:8]}"
        # 避免重复标题：如果 text 已经以 h1 开头则不重复加
        if text.startswith("# "):
            store.write_page(page_name, text)
        else:
            store.write_page(page_name, f"# {doc_title}\n\n{text}")

        # 更新 index
        existing = store.read_index()
        summaries = {}
        for line in existing.splitlines():
            if line.startswith("- **["):
                try:
                    n = line.split("[")[1].split("]")[0]
                    s = line.split("—")[-1].strip()
                    summaries[n] = s
                except (IndexError, ValueError):
                    pass
        summaries[page_name] = title.strip()[:80]
        store.update_index(summaries)

        now = _now()
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, chunk_count, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (page_name, "wiki_chat", doc_title, "", "chat_remember", 1, "indexed", now),
        )
        conn.commit()

        # 结构化双向链接：wiki_pages 表存源记忆引用，供反查（不再依赖正文文本解析）。
        try:
            db.upsert_wiki_page(
                page_name,
                title=doc_title,
                summary=(title.strip()[:80] if title else doc_title[:80]),
                source_memory_ids=list(source_memory_ids or []),
                source_type="chat_remember",
                tenant_id=tenant_id,
            )
        except Exception as link_err:
            print(f"[TurnKnowledgePublisher] wiki_pages link failed: {link_err}")

        return page_name
    except Exception as e:
        print(f"[TurnKnowledgePublisher] wiki write failed: {e}")
        return None
