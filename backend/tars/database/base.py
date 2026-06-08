# TARS Database Layer
# Database Facade — 对外签名零变更，内部委派给各 domain repository

import os
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from tars.database.models import (
    get_local_now, _parse_db_datetime,
    Session, Message, Memory, CronJob,
    ReminderNotification, Transcription, AuditLog, ApprovalRequest,
)
from tars.database.connection import ConnectionManager
from tars.database.repositories.session_repo import SessionRepo
from tars.database.repositories.memory_repo import MemoryRepo
from tars.database.repositories.cron_repo import CronRepo
from tars.database.repositories.trans_repo import TranscriptionRepo
from tars.database.repositories.wiki_repo import WikiRepo
from tars.database.auth_token_store import AuthTokenStore


class Database:
    """数据库门面。持有 ConnectionManager 和各 domain repository。"""

    def __init__(self, db_path: Optional[str] = None):
        self._cm = ConnectionManager(db_path)
        self.db_path = self._cm.db_path
        self.sessions = SessionRepo(self._cm)
        self.memories = MemoryRepo(self._cm)
        self.crons = CronRepo(self._cm)
        self.transcriptions = TranscriptionRepo(self._cm)
        self.wiki_pages = WikiRepo(self._cm)
        self.auth_tokens = AuthTokenStore(self)

    def _get_conn(self):
        return self._cm.get_conn()

    def close(self):
        self._cm.close()

    def create_session(self, *args, **kwargs):
        return self.sessions.create_session(*args, **kwargs)

    def get_session(self, *args, **kwargs):
        return self.sessions.get_session(*args, **kwargs)

    def get_session_metadata(self, *args, **kwargs):
        return self.sessions.get_session_metadata(*args, **kwargs)

    def set_session_metadata(self, *args, **kwargs):
        return self.sessions.set_session_metadata(*args, **kwargs)

    def add_message(self, *args, **kwargs):
        return self.sessions.add_message(*args, **kwargs)

    def get_messages(self, *args, **kwargs):
        return self.sessions.get_messages(*args, **kwargs)

    def list_sessions(self, *args, **kwargs):
        return self.sessions.list_sessions(*args, **kwargs)

    def delete_session(self, *args, **kwargs):
        return self.sessions.delete_session(*args, **kwargs)

    def update_session_title(self, *args, **kwargs):
        return self.sessions.update_session_title(*args, **kwargs)

    def add_memory(self, *args, **kwargs):
        return self.memories.add_memory(*args, **kwargs)

    def _memory_from_row(self, *args, **kwargs):
        return self.memories._memory_from_row(*args, **kwargs)

    def get_memory(self, *args, **kwargs):
        return self.memories.get_memory(*args, **kwargs)

    def _has_cjk(self, *args, **kwargs):
        return self.memories._has_cjk(*args, **kwargs)

    def search_memories(self, *args, **kwargs):
        return self.memories.search_memories(*args, **kwargs)

    def get_memories_by_category(self, *args, **kwargs):
        return self.memories.get_memories_by_category(*args, **kwargs)

    def get_recent_memories(self, *args, **kwargs):
        return self.memories.get_recent_memories(*args, **kwargs)

    def update_memory(self, *args, **kwargs):
        return self.memories.update_memory(*args, **kwargs)

    def reinforce_memory(self, *args, **kwargs):
        return self.memories.reinforce_memory(*args, **kwargs)

    def get_all_memories_with_metadata(self, *args, **kwargs):
        return self.memories.get_all_memories_with_metadata(*args, **kwargs)

    def set_memory_pin(self, *args, **kwargs):
        return self.memories.set_memory_pin(*args, **kwargs)

    def promote_memory(self, *args, **kwargs):
        return self.memories.promote_memory(*args, **kwargs)

    def set_memory_promotion_meta(self, *args, **kwargs):
        return self.memories.set_memory_promotion_meta(*args, **kwargs)

    def get_kb_promotion_group_stats(self, *args, **kwargs):
        return self.memories.get_kb_promotion_group_stats(*args, **kwargs)

    def list_memories_for_kb_promotion(self, *args, **kwargs):
        return self.memories.list_memories_for_kb_promotion(*args, **kwargs)

    def mark_memories_kb_published(self, *args, **kwargs):
        return self.memories.mark_memories_kb_published(*args, **kwargs)

    def list_kb_promotion_groups(self, *args, **kwargs):
        return self.memories.list_kb_promotion_groups(*args, **kwargs)

    def delete_memory(self, *args, **kwargs):
        return self.memories.delete_memory(*args, **kwargs)

    def get_memory_stats(self, *args, **kwargs):
        return self.memories.get_memory_stats(*args, **kwargs)

    def list_recent_memories(self, *args, **kwargs):
        return self.memories.list_recent_memories(*args, **kwargs)

    def list_longterm_memories(self, *args, **kwargs):
        return self.memories.list_longterm_memories(*args, **kwargs)

    def list_all_memories(self, *args, **kwargs):
        return self.memories.list_all_memories(*args, **kwargs)

    def list_memories_for_tree(self, *args, **kwargs):
        return self.memories.list_memories_for_tree(*args, **kwargs)

    def decay_importance(self, *args, **kwargs):
        return self.memories.decay_importance(*args, **kwargs)

    def cleanup_old_memories(self, *args, **kwargs):
        return self.memories.cleanup_old_memories(*args, **kwargs)

    def forget_core_line(self, *args, **kwargs):
        return self.memories.forget_core_line(*args, **kwargs)

    def get_document_file(self, *args, **kwargs):
        return self.transcriptions.get_document_file(*args, **kwargs)

    def update_document_file(self, *args, **kwargs):
        return self.transcriptions.update_document_file(*args, **kwargs)

    def delete_document_file(self, *args, **kwargs):
        return self.transcriptions.delete_document_file(*args, **kwargs)

    def _update_memory_access(self, *args, **kwargs):
        return self.memories._update_memory_access(*args, **kwargs)

    def get_all_memories_with_embeddings(self, *args, **kwargs):
        return self.memories.get_all_memories_with_embeddings(*args, **kwargs)

    def _row_to_cronjob(self, *args, **kwargs):
        return self.crons._row_to_cronjob(*args, **kwargs)

    def _row_to_reminder_notification(self, *args, **kwargs):
        return self.crons._row_to_reminder_notification(*args, **kwargs)

    def create_cronjob(self, *args, **kwargs):
        return self.crons.create_cronjob(*args, **kwargs)

    def get_cronjob(self, *args, **kwargs):
        return self.crons.get_cronjob(*args, **kwargs)

    def get_user_cronjobs(self, *args, **kwargs):
        return self.crons.get_user_cronjobs(*args, **kwargs)

    def get_enabled_cronjobs(self, *args, **kwargs):
        return self.crons.get_enabled_cronjobs(*args, **kwargs)

    def update_cronjob(self, *args, **kwargs):
        return self.crons.update_cronjob(*args, **kwargs)

    def delete_cronjob(self, *args, **kwargs):
        return self.crons.delete_cronjob(*args, **kwargs)

    def create_reminder_notification(self, *args, **kwargs):
        return self.crons.create_reminder_notification(*args, **kwargs)

    def list_reminder_notifications(self, *args, **kwargs):
        return self.crons.list_reminder_notifications(*args, **kwargs)

    def count_reminder_notifications(self, *args, **kwargs):
        return self.crons.count_reminder_notifications(*args, **kwargs)

    def count_unread_reminder_notifications(self, *args, **kwargs):
        return self.crons.count_unread_reminder_notifications(*args, **kwargs)

    def get_reminder_notification(self, *args, **kwargs):
        return self.crons.get_reminder_notification(*args, **kwargs)

    def mark_reminder_notification_read(self, *args, **kwargs):
        return self.crons.mark_reminder_notification_read(*args, **kwargs)

    def get_latest_reminder_notification_for_job(self, *args, **kwargs):
        return self.crons.get_latest_reminder_notification_for_job(*args, **kwargs)

    def get_working_context(self, *args, **kwargs):
        return self.sessions.get_working_context(*args, **kwargs)

    def upsert_working_context(self, *args, **kwargs):
        return self.sessions.upsert_working_context(*args, **kwargs)

    def cleanup_working_contexts(self, *args, **kwargs):
        return self.sessions.cleanup_working_contexts(*args, **kwargs)

    def add_dead_letter(self, *args, **kwargs):
        return self.memories.add_dead_letter(*args, **kwargs)

    def create_transcription(self, *args, **kwargs):
        return self.transcriptions.create_transcription(*args, **kwargs)

    def get_transcription(self, *args, **kwargs):
        return self.transcriptions.get_transcription(*args, **kwargs)

    def list_transcriptions(self, *args, **kwargs):
        return self.transcriptions.list_transcriptions(*args, **kwargs)

    def update_transcription(self, *args, **kwargs):
        return self.transcriptions.update_transcription(*args, **kwargs)

    def delete_transcription(self, *args, **kwargs):
        return self.transcriptions.delete_transcription(*args, **kwargs)

    def set_memory_scope(self, *args, **kwargs):
        return self.memories.set_memory_scope(*args, **kwargs)

    def find_memory_any_tenant(self, *args, **kwargs):
        return self.memories.find_memory_any_tenant(*args, **kwargs)

    def get_memory_scope(self, *args, **kwargs):
        return self.memories.get_memory_scope(*args, **kwargs)

    def add_audit_log(self, *args, **kwargs):
        return self.sessions.add_audit_log(*args, **kwargs)

    def create_approval_request(self, *args, **kwargs):
        return self.sessions.create_approval_request(*args, **kwargs)

    def get_approval_request(self, *args, **kwargs):
        return self.sessions.get_approval_request(*args, **kwargs)

    def update_approval_request(self, *args, **kwargs):
        return self.sessions.update_approval_request(*args, **kwargs)

    def list_pending_approval_requests(self, *args, **kwargs):
        return self.sessions.list_pending_approval_requests(*args, **kwargs)

    def list_audit_logs(self, *args, **kwargs):
        return self.sessions.list_audit_logs(*args, **kwargs)

    def _row_to_audit_log(self, *args, **kwargs):
        return self.sessions._row_to_audit_log(*args, **kwargs)

    def record_provider_usage(self, *args, **kwargs):
        return self.memories.record_provider_usage(*args, **kwargs)

    def list_provider_usage(self, *args, **kwargs):
        return self.memories.list_provider_usage(*args, **kwargs)

    def aggregate_provider_usage(self, *args, **kwargs):
        return self.memories.aggregate_provider_usage(*args, **kwargs)

    def _row_to_transcription(self, *args, **kwargs):
        return self.transcriptions._row_to_transcription(*args, **kwargs)

    def insert_evolution_event(self, *args, **kwargs):
        return self.memories.insert_evolution_event(*args, **kwargs)

    def list_evolution_events(self, *args, **kwargs):
        return self.memories.list_evolution_events(*args, **kwargs)

    def count_evolution_events(self, *args, **kwargs):
        return self.memories.count_evolution_events(*args, **kwargs)

    def insert_evolution_apply_log(self, *args, **kwargs):
        return self.memories.insert_evolution_apply_log(*args, **kwargs)

    def list_evolution_apply_logs_by_batch(self, *args, **kwargs):
        return self.memories.list_evolution_apply_logs_by_batch(*args, **kwargs)

    def count_insight_downvote_burst_metrics(self, *args, **kwargs):
        return self.memories.count_insight_downvote_burst_metrics(*args, **kwargs)

    def get_evolution_apply_log(self, *args, **kwargs):
        return self.memories.get_evolution_apply_log(*args, **kwargs)

    def insert_auth_token(self, jti: str, user_id: str, expires_at) -> None:
        return self.auth_tokens.insert_token(jti, user_id, expires_at)

    def revoke_auth_token(self, jti: str) -> None:
        return self.auth_tokens.revoke_token(jti)

    def is_auth_token_revoked(self, jti: str) -> bool:
        return self.auth_tokens.is_token_revoked(jti)

    def upsert_wiki_page(self, *args, **kwargs):
        return self.wiki_pages.upsert_wiki_page(*args, **kwargs)

    def get_wiki_page_meta(self, *args, **kwargs):
        return self.wiki_pages.get_wiki_page_meta(*args, **kwargs)

    def find_pages_by_memory_id(self, *args, **kwargs):
        return self.wiki_pages.find_pages_by_memory_id(*args, **kwargs)

    def execute(self, sql: str, params: tuple = ()) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()

    def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

