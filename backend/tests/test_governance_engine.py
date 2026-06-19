"""治理 engine 双引擎路由测试。"""
from tars.governance.result_set import ResultSet
from tars.governance.models import QualityRule
from tars.governance.engine import run_checks


def test_builtin_not_null_passes():
    rs = ResultSet(
        rows=[[1, "a"], [2, "b"], [3, "c"]],
        column_names=["id", "name"],
    )
    rules = [
        QualityRule(id="r1", datasource_id="ds1", kind="not_null",
                    name="名称非空", params={"field": "name"}),
    ]
    check_run, rows = run_checks(rs, rules, datasource_id="ds1", table_name="t")
    assert check_run.status == "passed"
    assert check_run.summary["total_passed"] == 3
    assert check_run.summary["total_failed"] == 0
    assert len(rows) == 1 and rows[0].failed_count == 0
    # ★ 验证 rule_results 在 summary 里（修复 Argus 遗留 bug）
    assert len(check_run.summary["rule_results"]) == 1


def test_builtin_not_null_detects_violation():
    rs = ResultSet(
        rows=[[1, "a"], [2, None], [3, ""]],
        column_names=["id", "name"],
    )
    rules = [
        QualityRule(id="r1", datasource_id="ds1", kind="not_null",
                    name="名称非空", params={"field": "name"}),
    ]
    check_run, rows = run_checks(rs, rules, datasource_id="ds1", table_name="t")
    assert check_run.status == "failed"
    assert rows[0].failed_count == 2
    assert check_run.summary["rule_results"][0]["sample_violations"]


def test_mixed_rules():
    rs = ResultSet(
        rows=[[1, "a"], [2, "b"], [3, "a"]],
        column_names=["id", "name"],
    )
    rules = [
        QualityRule(id="r1", datasource_id="ds1", kind="not_null",
                    name="notnull", params={"field": "name"}),
        QualityRule(id="r2", datasource_id="ds1", kind="unique",
                    name="unique", params={"field": "name"}),
    ]
    check_run, rows = run_checks(rs, rules, datasource_id="ds1", table_name="t")
    assert check_run.status == "failed"  # unique fails
    assert len(rows) == 2


def test_ge_not_available_is_graceful():
    rs = ResultSet(rows=[[1]], column_names=["id"])
    rules = [
        QualityRule(id="r1", datasource_id="ds1", kind="expect_column_values_to_not_be_null",
                    name="ge rule", engine="great_expectations",
                    params={"column": "id"}),
    ]
    check_run, rows = run_checks(rs, rules, datasource_id="ds1", table_name="t", ge_engine=None)
    assert check_run.status == "error"
    assert rows[0].failed_count == 0  # 优雅降级不设 failed
