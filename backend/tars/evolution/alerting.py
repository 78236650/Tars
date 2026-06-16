"""AlertEngine — 主动预警引擎。

v5.0.5/A4: 定时巡检 Memory，检测异常模式，通过 Channels outbound 推送通知。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..database.base import Database


@dataclass
class Alert:
    type: str  # "correction_burst" | "entity_stale" | "low_importance_surge"
    severity: str  # "info" | "warning" | "critical"
    title: str
    description: str
    entity: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertEngine:
    """定时巡检 Memory，生成预警。

    检测规则：
    1. correction_burst: ≥3 条同类纠正 → 用户反复纠正同一问题
    2. entity_stale: 某 entity 30 天无新记忆 → 提醒关注
    3. low_importance_surge: 最近 7 天大量低重要性 episodic → 可能碎片过多
    """

    CORRECTION_BURST_THRESHOLD = 3
    ENTITY_STALE_DAYS = 30
    LOW_IMPORTANCE_SURGE_THRESHOLD = 20

    def __init__(self, db: "Database"):
        self.db = db

    def scan(self, tenant_id: str) -> List[Alert]:
        """执行一轮巡检，返回预警列表。"""
        alerts: List[Alert] = []

        # 1. 检测 correction_burst
        correction_alerts = self._check_correction_burst(tenant_id)
        alerts.extend(correction_alerts)

        # 2. 检测 entity_stale
        stale_alerts = self._check_entity_stale(tenant_id)
        alerts.extend(stale_alerts)

        # 3. 检测低重要性碎片堆积
        surge_alerts = self._check_low_importance_surge(tenant_id)
        alerts.extend(surge_alerts)

        return alerts

    def _check_correction_burst(self, tenant_id: str) -> List[Alert]:
        """检测用户反复纠正同一问题。"""
        try:
            conn = self.db._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT content, COUNT(*) as cnt
                   FROM memories
                   WHERE tenant_id = ? AND category = 'correction'
                     AND created_at > datetime('now', '-30 days')
                   GROUP BY SUBSTR(content, 4, 20)
                   HAVING cnt >= ?
                   ORDER BY cnt DESC
                   LIMIT 5""",
                (tenant_id, self.CORRECTION_BURST_THRESHOLD),
            )
            alerts = []
            for content, cnt in cur.fetchall():
                # 提取纠正主题（"纠正：XXX"）
                theme = content.split("纠正：", 1)[1][:50] if "纠正：" in content else content[:50]
                alerts.append(Alert(
                    type="correction_burst",
                    severity="warning",
                    title=f"重复纠正：{theme}",
                    description=f"用户在过去30天内纠正了同一问题 {cnt} 次。建议检查 Agent 行为是否需要调整。",
                    metadata={"correction_count": cnt, "theme": theme},
                ))
            return alerts
        except Exception:
            return []

    def _check_entity_stale(self, tenant_id: str) -> List[Alert]:
        """检测长时间未更新的实体。"""
        try:
            conn = self.db._get_conn()
            cur = conn.cursor()
            cur.execute(
                f"""SELECT e.id, e.name, e.type, MAX(m.updated_at) as last_update
                    FROM entities e
                    LEFT JOIN memories m ON m.entity_refs LIKE '%' || e.id || '%'
                        AND m.tenant_id = ?
                    WHERE e.last_accessed < datetime('now', '-{self.ENTITY_STALE_DAYS} days')
                       OR e.last_accessed IS NULL
                    GROUP BY e.id
                    HAVING last_update < datetime('now', '-{self.ENTITY_STALE_DAYS} days')
                       OR last_update IS NULL
                    LIMIT 5""",
                (tenant_id,),
            )
            alerts = []
            for eid, name, etype, last_update in cur.fetchall():
                alerts.append(Alert(
                    type="entity_stale",
                    severity="info",
                    title=f"实体久未更新：{name or eid}",
                    description=f"「{name or eid}」({etype}) 已超过 {self.ENTITY_STALE_DAYS} 天无新记忆。",
                    entity=eid,
                    metadata={"entity_type": etype, "last_update": last_update},
                ))
            return alerts
        except Exception:
            return []

    def _check_low_importance_surge(self, tenant_id: str) -> List[Alert]:
        """检测低重要性 episodic 碎片堆积。"""
        try:
            conn = self.db._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT COUNT(*) FROM memories
                   WHERE tenant_id = ? AND importance < 0.4
                     AND created_at > datetime('now', '-7 days')""",
                (tenant_id,),
            )
            count = cur.fetchone()[0]
            if count >= self.LOW_IMPORTANCE_SURGE_THRESHOLD:
                return [Alert(
                    type="low_importance_surge",
                    severity="info",
                    title=f"记忆碎片堆积：{count} 条",
                    description=f"最近 7 天产生了 {count} 条低重要性 episodic 记忆。建议运行 cleanup 或检查 Reflector 提取质量。",
                    metadata={"count": count, "days": 7},
                )]
            return []
        except Exception:
            return []
