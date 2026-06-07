"""Publish InsightForge glossary to TARS knowledge base."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from ..database.base import Database, get_local_now
from ..org import ORG_ID
from .version import CAPABILITY_NAME, INS_VERSION

logger = logging.getLogger(__name__)


class KnowledgePublisher:
    def __init__(self, db: Database, knowledge_indexer=None):
        self.db = db
        self.indexer = knowledge_indexer

    def collection_id_for(self, datasource_id: str) -> str:
        return f"insight_{datasource_id}"

    def ensure_collection(self, collection_id: str, name: str, tenant_id: str = ORG_ID) -> None:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, tenant_id FROM document_collections WHERE id = ?",
            (collection_id,),
        )
        row = cursor.fetchone()
        now = get_local_now().isoformat()
        if row:
            if row[1] != tenant_id:
                raise PermissionError(
                    f"collection {collection_id} belongs to tenant {row[1]!r}, refusing to rewrite to {tenant_id!r}"
                )
            return
        cursor.execute(
            """
            INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                collection_id,
                tenant_id,
                name,
                f"InsightForge 鉴数知识库 {INS_VERSION}",
                now,
                now,
            ),
        )
        conn.commit()

    def render_markdown(
        self,
        datasource_name: str,
        schema: Dict[str, Any],
        annotations: Dict[str, Any],
        relations: List[Any],
        table_roles: Dict[str, str],
        quality_flags: List[Dict[str, Any]],
        open_questions: List[str],
        llm_errors: Optional[List[str]] = None,
    ) -> str:
        lines = [
            f"# {datasource_name} 业务数据说明书",
            "",
            f"- **能力**: {CAPABILITY_NAME} `{INS_VERSION}`",
            f"- **表数量**: {len(schema.get('tables') or {})}",
            "",
            "## 实体关系",
            "",
        ]
        if relations:
            lines.append("```mermaid")
            lines.append("erDiagram")
            for rel in relations[:40]:
                fr = rel.from_ref if hasattr(rel, "from_ref") else rel.get("from_ref", "")
                to = rel.to_ref if hasattr(rel, "to_ref") else rel.get("to_ref", "")
                if fr and to:
                    a, ac = fr.split(".", 1) if "." in fr else (fr, "id")
                    b, bc = to.split(".", 1) if "." in to else (to, "id")
                    lines.append(f"  {a} }}o--|| {b} : {ac}")
            lines.append("```")
        else:
            lines.append("（未发现高置信关系）")

        lines.extend(["", "## 核心表", ""])
        for table, ann in list(annotations.items())[:40]:
            role = table_roles.get(table, "")
            desc = ann.get("description", "") if isinstance(ann, dict) else ""
            lines.append(f"### {table} ({role})")
            lines.append(desc or "")
            cols = ann.get("columns") if isinstance(ann, dict) else {}
            if cols:
                lines.append("")
                lines.append("| 列 | 含义 |")
                lines.append("|----|------|")
                for cn, label in list(cols.items())[:30]:
                    lines.append(f"| {cn} | {label} |")
            lines.append("")

        if quality_flags:
            lines.extend(["## 数据质量告警", ""])
            for q in quality_flags[:20]:
                lines.append(f"- {q.get('table')}.{q.get('column')}: {q.get('issue')} = {q.get('value')}")

        if llm_errors:
            lines.extend(["## 建档告警（大模型）", ""])
            for err in llm_errors:
                lines.append(f"- {err}")

        if open_questions:
            lines.extend(["## 待业务确认", ""])
            for q in open_questions:
                lines.append(f"- {q}")

        return "\n".join(lines)

    def publish(
        self,
        datasource_id: str,
        datasource_name: str,
        markdown: str,
        tenant_id: str = ORG_ID,
        run_id: Optional[str] = None,
        metric_ids: Optional[List[str]] = None,
    ) -> Optional[str]:
        coll_id = self.collection_id_for(datasource_id)
        self.ensure_collection(coll_id, f"鉴数-{datasource_name}", tenant_id)
        doc_id = f"insight_{datasource_id}_{uuid.uuid4().hex[:8]}"
        version_suffix = f"_v{run_id[:8]}" if run_id else ""
        file_name = f"insightforge_{datasource_name}{version_suffix}.md"

        if self.indexer is None:
            return doc_id

        result = self.indexer.index_document(
            text=markdown,
            doc_id=doc_id,
            collection_id=coll_id,
            file_name=file_name,
            file_type="md",
            tenant_id=tenant_id,
        )
        if isinstance(result, dict) and result.get("status") in ("indexed", "no_chunks", "empty"):
            return doc_id
        logger.warning(
            "[InsightForge] knowledge indexing failed for ds=%s: %s", datasource_id, result
        )
        return None
