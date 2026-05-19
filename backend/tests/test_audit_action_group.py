"""Audit action_group filter."""
import pytest

from tars.database import Database
from tars.security.audit import AuditLogger


@pytest.fixture
def audit_db(tmp_path):
    db = Database(db_path=str(tmp_path / "audit.db"))
    logger = AuditLogger(db)
    logger.log_skill_event("skill_install", "demo/pdf", tenant_id="t1", user_id="admin")
    logger.log_bi_query("ds-1", tenant_id="t1", user_id="admin", sql_hash="abc", row_count=3)
    logger.log(action="login", resource_type="user", tenant_id="t1", user_id="admin")
    yield db
    db.close()


def test_list_audit_logs_action_group_skill(audit_db):
    logs, total = audit_db.list_audit_logs(actions=["skill_install", "skill_uninstall"])
    assert total == 1
    assert logs[0].action == "skill_install"


def test_list_audit_logs_action_group_bi(audit_db):
    logs, total = audit_db.list_audit_logs(actions=["bi_query"])
    assert total == 1
    assert logs[0].action == "bi_query"
