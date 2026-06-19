"""治理校验引擎 — builtin + GE 双引擎，在 ResultSet 上跑规则。"""
from __future__ import annotations

import uuid

from .rules import get_rule_fn
from .rules.builtin import RuleResult as BuiltinRuleResult
from .result_set import ResultSet
from .models import QualityRule, CheckRun, RuleResultRow


def run_checks(
    result_set: ResultSet,
    rules: list[QualityRule],
    *,
    datasource_id: str,
    table_name: str = "",
    user_id: str = "default",
    ge_engine=None,
) -> tuple[CheckRun, list[RuleResultRow]]:
    """在 ResultSet 上执行规则，返回 (CheckRun 汇总, 单规则结果行列表)。"""
    total_passed = 0
    total_failed = 0
    result_rows: list[RuleResultRow] = []
    errors: list[str] = []
    run_id = str(uuid.uuid4())

    builtin_rules = [r for r in rules if r.engine == "builtin" and r.enabled]
    ge_rules = [r for r in rules if r.engine == "great_expectations" and r.enabled]

    # ── builtin ──
    for rule in builtin_rules:
        try:
            fn = get_rule_fn(rule.kind)
            res: BuiltinRuleResult = fn(result_set.rows, result_set.column_names, rule.params)
            result_rows.append(RuleResultRow(
                id=str(uuid.uuid4()), check_run_id=run_id, rule_id=rule.id,
                rule_name=rule.name, kind=rule.kind, engine="builtin",
                passed_count=res.passed_count, failed_count=res.failed_count,
                sample_violations=res.sample_violations,
            ))
            total_passed += res.passed_count
            total_failed += res.failed_count
        except Exception as e:
            result_rows.append(RuleResultRow(
                id=str(uuid.uuid4()), check_run_id=run_id, rule_id=rule.id,
                rule_name=rule.name, kind=rule.kind, engine="builtin",
            ))
            errors.append(f"Rule '{rule.name}' failed: {e}")

    # ── GE ──
    if ge_rules and ge_engine is not None:
        try:
            import pandas as pd
            df = pd.DataFrame(result_set.rows, columns=result_set.column_names)
            suite = ge_engine.create_suite("tars_check", [
                {"type": r.kind, "kwargs": r.params} for r in ge_rules
            ])
            ge_result = ge_engine.validate(suite, df)
            for i, r in enumerate(ge_rules):
                ge_rr = ge_result["results"][i] if i < len(ge_result["results"]) else {}
                ok = ge_rr.get("success", False)
                result_rows.append(RuleResultRow(
                    id=str(uuid.uuid4()), check_run_id=run_id, rule_id=r.id,
                    rule_name=r.name, kind=r.kind, engine="great_expectations",
                    passed_count=ge_rr.get("result", {}).get("element_count", 0) if ok else 0,
                    failed_count=0 if ok else 1,
                    sample_violations=ge_rr.get("result", {}).get("unexpected_list", [])[:20],
                ))
                total_passed += result_rows[-1].passed_count
                total_failed += result_rows[-1].failed_count
        except Exception as e:
            errors.append(f"GE engine failed: {e}")
    elif ge_rules and ge_engine is None:
        for r in ge_rules:
            result_rows.append(RuleResultRow(
                id=str(uuid.uuid4()), check_run_id=run_id, rule_id=r.id,
                rule_name=r.name, kind=r.kind, engine="great_expectations",
            ))
            errors.append(f"GE rule '{r.name}' skipped: great_expectations not installed")

    # ── 汇总 ──
    status = "error" if errors else ("passed" if total_failed == 0 else "failed")

    check_run = CheckRun(
        id=run_id,
        datasource_id=datasource_id,
        table_name=table_name,
        status=status,
        total_rows=len(result_set.rows),
        truncated=result_set.truncated,
        summary={
            "total_passed": total_passed,
            "total_failed": total_failed,
            "rules_checked": len(rules),
            "rules_passed": len([r for r in result_rows if r.failed_count == 0]),
            "rules_failed": len([r for r in result_rows if r.failed_count > 0]),
            "errors": errors,
            # ★ 修复 Argus 遗留 bug：engine 必须把 rule_results 写进 summary
            "rule_results": [
                {
                    "rule_id": rr.rule_id,
                    "rule_name": rr.rule_name,
                    "kind": rr.kind,
                    "engine": rr.engine,
                    "passed_count": rr.passed_count,
                    "failed_count": rr.failed_count,
                    "sample_violations": rr.sample_violations,
                }
                for rr in result_rows
            ],
        },
        error="; ".join(errors) if errors else None,
        user_id=user_id,
    )
    return check_run, result_rows
