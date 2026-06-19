"""治理 repository CRUD 测试。"""
import uuid

from tars.governance.repository import GovernanceRepository
from tars.governance.models import CheckRun, RuleResultRow


def test_create_and_list_rule(test_db):
    repo = GovernanceRepository(test_db)
    rule = repo.create_rule(datasource_id="ds1", kind="not_null",
                            name="名称非空", table_name="items",
                            params={"field": "name"}, user_id="u1")
    assert rule.id
    rules = repo.list_rules(datasource_id="ds1", user_id="u1")
    assert len(rules) == 1 and rules[0].kind == "not_null"
    assert rules[0].params == {"field": "name"}


def test_user_isolation(test_db):
    repo = GovernanceRepository(test_db)
    repo.create_rule(datasource_id="ds1", kind="unique", params={"field": "id"}, user_id="u1")
    assert repo.list_rules(datasource_id="ds1", user_id="u2") == []


def test_save_and_get_check_run(test_db):
    repo = GovernanceRepository(test_db)
    run = CheckRun(id=str(uuid.uuid4()), datasource_id="ds1", table_name="items",
                   status="passed", total_rows=10, user_id="u1")
    rr = RuleResultRow(id=str(uuid.uuid4()), check_run_id=run.id, rule_id="r1",
                       rule_name="x", kind="not_null", passed_count=10)
    repo.save_check_run(run, [rr])
    got = repo.get_check_run(run.id, user_id="u1")
    assert got is not None and got.status == "passed" and got.total_rows == 10
