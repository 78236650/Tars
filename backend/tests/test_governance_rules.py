"""6 类 builtin 规则纯函数测试。"""
from tars.governance.rules.builtin import (
    validate_not_null, validate_unique, validate_range,
    validate_regex, validate_enum, validate_cross_field,
)

COLS = ["id", "name", "age", "start", "end", "status"]
ROWS = [
    [1, "a", 10, 1, 5, "ok"],
    [2, "",  20, 3, 2, "bad"],   # name 空; start>end
    [3, "a", 99, 1, 9, "ok"],    # name 重复; age 超范围
]


def test_not_null():
    r = validate_not_null([row[:2] for row in ROWS], ["id", "name"], {"field": "name"})
    assert r.failed_count == 1 and r.passed_count == 2


def test_unique():
    r = validate_unique([[row[1]] for row in ROWS], ["name"], {"field": "name"})
    assert r.failed_count == 1  # 第三行 "a" 重复


def test_range():
    r = validate_range([[row[2]] for row in ROWS], ["age"], {"field": "age", "min": 0, "max": 60})
    assert r.failed_count == 1  # 99 超范围


def test_regex():
    r = validate_regex([[row[5]] for row in ROWS], ["status"], {"field": "status", "pattern": r"^ok$"})
    assert r.failed_count == 1  # "bad"


def test_enum():
    r = validate_enum([[row[5]] for row in ROWS], ["status"], {"field": "status", "values": ["ok"]})
    assert r.failed_count == 1


def test_cross_field():
    r = validate_cross_field(
        [[row[3], row[4]] for row in ROWS], ["start", "end"],
        {"left": "start", "right": "end", "op": "<="},
    )
    assert r.failed_count == 1  # 第二行 start=3 > end=2


def test_field_not_found_is_graceful():
    r = validate_not_null(ROWS, COLS, {"field": "nonexistent"})
    assert r.sample_violations and "error" in r.sample_violations[0]
