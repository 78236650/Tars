"""Audit store unit tests — v4.3.2"""
from tars.database.audit_store import VerificationAuditStore
from tars.database.base import Database
from tars.orchestration.verification import VerifyResult, VerifyStepResult


def test_record_and_list(tmp_path):
    db = Database(str(tmp_path / "audit.db"))
    store = VerificationAuditStore(db)
    store.ensure_schema()

    result = VerifyResult(
        passed=True,
        status="pass",
        step_results=[
            VerifyStepResult(
                command="echo OK",
                expect='stdout contains "OK"',
                passed=True,
                message="ok",
            )
        ],
    )
    store.record("plan-1", "deploy", result)
    items = store.list_by_plan("plan-1")
    assert len(items) == 1
    assert items[0]["passed"] is True
    assert items[0]["skill_id"] == "deploy"
