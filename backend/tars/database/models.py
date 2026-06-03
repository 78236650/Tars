# TARS Database Models
# 数据类定义 + 工具函数（从 base.py 拆分出来）

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


def get_local_now():
    """获取本地时间（北京时间 UTC+8）"""
    return datetime.now(timezone(timedelta(hours=8)))


def _parse_db_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


@dataclass
class Session:
    id: str
    agent_id: str = "default"
    user_id: str = "default"
    tenant_id: str = "default"
    title: str = "New Session"
    created_at: datetime = None
    updated_at: datetime = None
    summary: Optional[str] = None
    metadata_json: Optional[dict] = None


@dataclass
class Message:
    id: str
    session_id: str
    role: str  # user, assistant, tool, system
    content: str
    timestamp: datetime = None
    metadata_json: Optional[dict] = None  # 用于存储 reasoning_content 等扩展信息


@dataclass
class Memory:
    id: str
    content: str
    category: str  # user_preference, project_record, important_decision, general
    tenant_id: str = "default"
    importance: float = 0.5  # 0-1
    created_at: datetime = None
    updated_at: datetime = None
    last_accessed: Optional[datetime] = None
    source: str = "conversation"
    pinned: bool = False
    compressed_from: Optional[List[str]] = None
    memory_type: str = "episodic"
    event_time: Optional[datetime] = None
    entity_refs: Optional[List[str]] = None
    scope: str = "private"
    user_id: Optional[str] = None
    promotion_group_id: Optional[str] = None
    kb_doc_id: Optional[str] = None
    kb_promotion_status: Optional[str] = None  # pending | published | skipped


@dataclass
class CronJob:
    id: str
    user_id: str
    name: str
    description: Optional[str]
    cron_expression: str
    task_type: str  # prompt, delegate, reminder
    task_config: str  # JSON 配置
    enabled: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


@dataclass
class ReminderNotification:
    id: str
    user_id: str
    job_id: str
    session_id: Optional[str]
    task_name: str
    message: str
    delivery_status: str
    error_message: Optional[str] = None
    summary_logs: List[Dict[str, Any]] = None
    is_read: bool = False
    triggered_at: datetime = None
    read_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class Transcription:
    id: str
    user_id: str
    file_path: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    language: Optional[str] = None
    status: str = "pending"
    transcript: Optional[str] = None
    segments: Optional[str] = None
    summary: Optional[str] = None
    summary_type: Optional[str] = None
    key_points: Optional[str] = None
    model_used: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    approved_at: Optional[str] = None
    knowledge_doc_id: Optional[str] = None


@dataclass
class AuditLog:
    id: str
    tenant_id: str = "default"
    user_id: str = "default"
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    detail: str = ""
    client_ip: str = ""
    created_at: datetime = None


@dataclass
class ApprovalRequest:
    id: str
    tenant_id: str = "default"
    user_id: str = "default"
    session_id: str = ""
    tool_name: str = ""
    arguments: str = "{}"
    status: str = "pending"
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: str = ""
