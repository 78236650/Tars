"""治理三表迁移建表测试。"""


def test_governance_tables_exist(test_db):
    conn = test_db._get_conn()
    cur = conn.cursor()
    for tbl in ("quality_rules", "check_runs", "rule_results"):
        cur.execute(f"SELECT * FROM {tbl} LIMIT 0")  # 不报错即表存在
