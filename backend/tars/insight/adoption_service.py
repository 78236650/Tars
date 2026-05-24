"""Metric adoption and feedback-driven downgrade (INS-2.0 M4)."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..database.base import Database, get_local_now
from ..database.bi_store import DataSourceStore
from .config import InsightConfig, get_insight_config
from .question_log_store import InsightQuestionLogStore
from .store import AdoptionConflictError, InsightMetricStore
from .models import InsightMetric

logger = logging.getLogger(__name__)


class AdoptionService:
    def __init__(
        self,
        db: Database,
        config: Optional[InsightConfig] = None,
        knowledge_bridge=None,
    ):
        self.db = db
        self.config = config or get_insight_config()
        self.metric_store = InsightMetricStore(db)
        self.question_log = InsightQuestionLogStore(db)
        self._knowledge_bridge = knowledge_bridge

    def adopt(
        self,
        metric_id: str,
        tenant_id: str,
        user_id: str,
        *,
        definition: Optional[str] = None,
        sql_template: Optional[str] = None,
        question_log_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        metric = self.metric_store.get_by_id(metric_id, tenant_id) if metric_id else None
        if not metric and question_log_id:
            metric = self._bootstrap_from_log(question_log_id, tenant_id)
            metric_id = metric.id

        if not metric:
            raise ValueError("metric not found")

        if self.config.adoption.require_review:
            return self._submit_for_review(
                metric_id, tenant_id, user_id, definition, sql_template
            )

        try:
            approved = self.metric_store.adopt_metric(
                metric_id,
                tenant_id,
                definition=definition,
                sql_template=sql_template,
            )
        except AdoptionConflictError as e:
            raise AdoptionConflictError(str(e)) from e

        self._audit(
            tenant_id,
            user_id,
            "insight_adopt",
            approved.id,
            {
                "metric_key": approved.metric_key,
                "version": approved.version,
                "status": approved.status,
            },
        )
        if self.config.adoption.publish_to_knowledge and self._knowledge_bridge:
            try:
                ds = DataSourceStore(self.db).get(approved.datasource_id, tenant_id)
                ds_name = ds.name if ds else approved.datasource_id
                doc_id = self._knowledge_bridge.publish_metric_card(
                    approved.datasource_id,
                    ds_name,
                    tenant_id,
                    approved,
                )
                if not doc_id:
                    self._audit(
                        tenant_id,
                        user_id,
                        "knowledge_publish_failed",
                        approved.id,
                        {"metric_key": approved.metric_key},
                    )
            except Exception as exc:
                logger.warning("publish_metric_card failed: %s", exc)
                self._audit(
                    tenant_id,
                    user_id,
                    "knowledge_publish_failed",
                    approved.id,
                    {"error": str(exc)},
                )
        return {"metric": self._metric_dict(approved), "status": "approved"}

    def _bootstrap_from_log(self, question_log_id: str, tenant_id: str) -> InsightMetric:
        log = self.question_log.get_log(question_log_id, tenant_id)
        if not log:
            raise ValueError("question log not found")
        key = (log.get("metric_key") or "").strip() or f"adhoc_{question_log_id[:8]}"
        existing = self.metric_store.get_current_by_key(
            log["datasource_id"], tenant_id, key
        )
        if existing and existing.status in ("draft", "approved"):
            return existing
        return self.metric_store.create_draft_from_log(
            datasource_id=log["datasource_id"],
            tenant_id=tenant_id,
            metric_key=key,
            display_name=key,
            definition=log.get("question") or key,
            sql_template=log.get("sql") or "",
            source="adhoc",
        )

    def _submit_for_review(
        self,
        metric_id: str,
        tenant_id: str,
        user_id: str,
        definition: Optional[str],
        sql_template: Optional[str],
    ) -> Dict[str, Any]:
        adoption_id = str(uuid.uuid4())
        now = get_local_now().isoformat()
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO insight_metric_adoptions (
                id, metric_id, proposed_by, status, reviewer_id, review_note, created_at, reviewed_at
            ) VALUES (?, ?, ?, 'pending', NULL, NULL, ?, NULL)
            """,
            (adoption_id, metric_id, user_id, now),
        )
        conn.commit()
        self._audit(
            tenant_id,
            user_id,
            "insight_adoption_review",
            adoption_id,
            {"metric_id": metric_id, "definition": definition, "sql_template": sql_template},
        )
        return {
            "adoption_id": adoption_id,
            "status": "pending_review",
            "code": "INSIGHT_ADOPTION_PENDING_REVIEW",
        }

    def list_pending_adoptions(self, tenant_id: str) -> List[Dict[str, Any]]:
        if not self.config.adoption.require_review:
            return []
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.id, a.metric_id, a.proposed_by, a.created_at,
                   m.datasource_id, m.metric_key, m.display_name, m.definition
            FROM insight_metric_adoptions a
            JOIN insight_metrics m ON m.id = a.metric_id
            WHERE a.status = 'pending' AND m.tenant_id = ?
            ORDER BY a.created_at DESC
            """,
            (tenant_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "adoption_id": r[0],
                "metric_id": r[1],
                "proposed_by": r[2],
                "created_at": r[3],
                "datasource_id": r[4],
                "metric_key": r[5],
                "display_name": r[6],
                "definition": r[7],
            }
            for r in rows
        ]

    def process_feedback(
        self, question_log_id: str, tenant_id: str, feedback: int, user_id: str
    ) -> Dict[str, Any]:
        log = self.question_log.get_log(question_log_id, tenant_id)
        if not log:
            return {"success": False}

        downgraded = False
        if feedback < 0 and log.get("metric_key"):
            downgraded = self._maybe_auto_downgrade(
                log["datasource_id"],
                tenant_id,
                log["metric_key"],
                user_id,
            )

        self._audit(
            tenant_id,
            user_id,
            "insight_feedback",
            question_log_id,
            {"feedback": feedback, "metric_key": log.get("metric_key"), "downgraded": downgraded},
        )
        return {"success": True, "downgraded": downgraded}

    def _maybe_auto_downgrade(
        self, datasource_id: str, tenant_id: str, metric_key: str, user_id: str
    ) -> bool:
        fb = self.config.feedback
        if self._in_downgrade_cooldown(datasource_id, tenant_id, metric_key, fb.downgrade_cooldown_days):
            return False

        stats = self.question_log.feedback_stats_for_metric(
            datasource_id, tenant_id, metric_key, fb.downgrade_window_days
        )
        down = stats["down"]
        up = stats["up"]
        total = down + up
        if down < fb.downgrade_min_down:
            return False
        if total == 0 or (down / total) < fb.downgrade_ratio_min:
            return False

        metric = self.metric_store.get_current_by_key(datasource_id, tenant_id, metric_key)
        if not metric or metric.status != "approved":
            return False

        if self.metric_store.deprecate_metric(metric.id, tenant_id):
            self._set_downgrade_cooldown(datasource_id, tenant_id, metric_key)
            self._audit(
                tenant_id,
                user_id,
                "insight_metric_status_change",
                metric.id,
                {"metric_key": metric_key, "from": "approved", "to": "deprecated", "reason": "H3"},
            )
            return True
        return False

    def _in_downgrade_cooldown(
        self, datasource_id: str, tenant_id: str, metric_key: str, cooldown_days: int
    ) -> bool:
        ts = self._get_cooldown_ts(datasource_id, tenant_id, metric_key)
        if not ts:
            return False
        try:
            last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return False
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - last.astimezone(timezone.utc)) < timedelta(days=cooldown_days)

    def _get_cooldown_ts(self, datasource_id: str, tenant_id: str, metric_key: str) -> Optional[str]:
        from ..database.bi_store import DataSourceStore

        ds_store = DataSourceStore(self.db)
        ds = ds_store.get(datasource_id, tenant_id)
        if not ds:
            return None
        insight = (ds.schema_snapshot or {}).get("insight") or {}
        cooldowns = insight.get("downgrade_cooldowns") or {}
        return cooldowns.get(metric_key)

    def _set_downgrade_cooldown(
        self, datasource_id: str, tenant_id: str, metric_key: str
    ) -> None:
        from ..database.bi_store import DataSourceStore

        ds_store = DataSourceStore(self.db)
        ds = ds_store.get(datasource_id, tenant_id)
        if not ds:
            return
        snapshot = dict(ds.schema_snapshot or {})
        insight = dict(snapshot.get("insight") or {})
        cooldowns = dict(insight.get("downgrade_cooldowns") or {})
        cooldowns[metric_key] = get_local_now().isoformat()
        insight["downgrade_cooldowns"] = cooldowns
        snapshot["insight"] = insight
        ds_store.update(datasource_id, tenant_id, schema_snapshot=snapshot)

    def _audit(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_id: str,
        detail: Dict[str, Any],
    ) -> None:
        try:
            self.db.add_audit_log(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource_type="insight_metric",
                resource_id=resource_id,
                detail=json.dumps(detail, ensure_ascii=False),
            )
        except Exception:
            pass

    @staticmethod
    def _metric_dict(m: InsightMetric) -> Dict[str, Any]:
        return {
            "id": m.id,
            "metric_key": m.metric_key,
            "display_name": m.display_name,
            "definition": m.definition,
            "status": m.status,
            "version": m.version,
            "superseded_by": m.superseded_by,
        }
