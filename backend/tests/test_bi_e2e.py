"""
BI Analytics Skill 端到端测试
覆盖：数据源创建 → 连接测试 → Schema 抓取 → SQL 查询 → 图表生成
使用 SQLite 内存数据库模拟真实业务场景
"""
import pytest
import json
import sqlite3
import tempfile
import os
from pathlib import Path

from tars.bi.sql_agent import SQLAgent
from tars.bi.security import SQLSecurityChecker
from tars.bi.schema_explorer import SchemaExplorer
from tars.bi.chart_generator import ChartGenerator
from tars.database.base import Database
from tars.database.bi_store import DataSourceStore


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_db_path():
    """创建一个带有示例业务数据的 SQLite 数据库"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    cur = conn.cursor()

    # 产品线表
    cur.execute("""
        CREATE TABLE product_lines (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)
    cur.executemany("INSERT INTO product_lines VALUES (?, ?, ?)", [
        (1, "A", "智能硬件"),
        (2, "B", "云服务"),
        (3, "C", "企业软件"),
    ])

    # 订单表
    cur.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            product_line TEXT NOT NULL,
            gmv REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    orders = [
        (1, 101, "A", 1500.0, "2026-04-01"),
        (2, 102, "B", 2300.0, "2026-04-02"),
        (3, 103, "A", 800.0, "2026-04-05"),
        (4, 101, "C", 4200.0, "2026-04-07"),
        (5, 104, "B", 1900.0, "2026-04-10"),
        (6, 102, "A", 3100.0, "2026-04-12"),
        (7, 105, "C", 2700.0, "2026-04-15"),
        (8, 103, "B", 1100.0, "2026-04-18"),
        (9, 106, "A", 950.0, "2026-04-20"),
        (10, 104, "C", 5500.0, "2026-04-25"),
    ]
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)

    # 用户表
    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            region TEXT
        )
    """)
    cur.executemany("INSERT INTO users VALUES (?, ?, ?, ?)", [
        (101, "张三", "zhang@test.com", "华东"),
        (102, "李四", "li@test.com", "华北"),
        (103, "王五", "wang@test.com", "华南"),
        (104, "赵六", "zhao@test.com", "华东"),
        (105, "钱七", "qian@test.com", "西南"),
        (106, "孙八", "sun@test.com", "华北"),
    ])

    conn.commit()
    conn.close()

    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_db_url(sample_db_path):
    return f"sqlite:///{sample_db_path}"


@pytest.fixture
def tars_db():
    db = Database(":memory:")
    yield db
    db.close()


@pytest.fixture
def ds_store(tars_db):
    return DataSourceStore(tars_db)


# ============================================================
# 1. 数据源连接测试
# ============================================================

class TestDataSourceConnection:
    """测试数据源创建和连接"""

    def test_create_datasource(self, ds_store, sample_db_url):
        """创建数据源并持久化"""
        ds = ds_store.create(
            tenant_id="tenant_1",
            name="测试订单库",
            db_type="sqlite",
            connection_url=sample_db_url,
        )
        assert ds.id is not None
        assert ds.name == "测试订单库"
        assert ds.db_type == "sqlite"
        assert ds.readonly == 1

    def test_list_datasources_by_tenant(self, ds_store, sample_db_url):
        """租户隔离：只能看到自己的数据源"""
        ds_store.create(tenant_id="t1", name="T1库", db_type="sqlite", connection_url=sample_db_url)
        ds_store.create(tenant_id="t2", name="T2库", db_type="sqlite", connection_url=sample_db_url)

        t1_list = ds_store.list_by_tenant("t1")
        t2_list = ds_store.list_by_tenant("t2")
        assert len(t1_list) == 1
        assert t1_list[0].name == "T1库"
        assert len(t2_list) == 1
        assert t2_list[0].name == "T2库"

    def test_connection_success(self, sample_db_url):
        """测试连接成功"""
        explorer = SchemaExplorer(sample_db_url)
        success, msg = explorer.test_connection()
        explorer.close()
        assert success is True

    def test_connection_failure(self):
        """测试连接失败"""
        explorer = SchemaExplorer("sqlite:///nonexistent_path_xyz.db")
        success, msg = explorer.test_connection()
        explorer.close()
        # SQLite 会自动创建文件，所以用无效 URL 测试
        bad_explorer = SchemaExplorer("postgresql+psycopg2://bad:bad@localhost:1/nope")
        bad_success, bad_msg = bad_explorer.test_connection()
        bad_explorer.close()
        assert bad_success is False


# ============================================================
# 2. Schema 抓取测试
# ============================================================

class TestSchemaExploration:
    """测试 Schema 自动抓取"""

    def test_explore_tables(self, sample_db_url):
        """抓取所有表结构"""
        explorer = SchemaExplorer(sample_db_url)
        schema = explorer.explore()
        explorer.close()

        assert "tables" in schema
        tables = schema["tables"]
        assert "orders" in tables
        assert "users" in tables
        assert "product_lines" in tables

    def test_explore_columns(self, sample_db_url):
        """抓取列信息"""
        explorer = SchemaExplorer(sample_db_url)
        schema = explorer.explore()
        explorer.close()

        orders_cols = schema["tables"]["orders"]["columns"]
        col_names = [c["name"] for c in orders_cols]
        assert "id" in col_names
        assert "user_id" in col_names
        assert "product_line" in col_names
        assert "gmv" in col_names
        assert "created_at" in col_names

    def test_explore_primary_key(self, sample_db_url):
        """抓取主键"""
        explorer = SchemaExplorer(sample_db_url)
        schema = explorer.explore()
        explorer.close()

        pk = schema["tables"]["orders"].get("primary_key", [])
        assert "id" in pk


# ============================================================
# 3. SQL 安全校验测试
# ============================================================

class TestSQLSecurity:
    """测试 SQL 安全层"""

    def setup_method(self):
        self.checker = SQLSecurityChecker(max_rows=1000, timeout_seconds=30)

    def test_select_allowed(self):
        valid, err = self.checker.validate("SELECT * FROM orders")
        assert valid is True

    def test_select_with_cte_allowed(self):
        sql = "WITH t AS (SELECT * FROM orders) SELECT * FROM t"
        valid, err = self.checker.validate(sql)
        assert valid is True

    def test_insert_blocked(self):
        valid, err = self.checker.validate("INSERT INTO orders VALUES (99, 1, 'A', 100, '2026-01-01')")
        assert valid is False
        assert err  # 有错误信息

    def test_update_blocked(self):
        valid, err = self.checker.validate("UPDATE orders SET gmv = 0")
        assert valid is False

    def test_delete_blocked(self):
        valid, err = self.checker.validate("DELETE FROM orders")
        assert valid is False

    def test_drop_blocked(self):
        valid, err = self.checker.validate("DROP TABLE orders")
        assert valid is False

    def test_multi_statement_blocked(self):
        valid, err = self.checker.validate("SELECT 1; DROP TABLE orders")
        assert valid is False

    def test_add_limit(self):
        sql = "SELECT * FROM orders"
        limited = self.checker.add_limit(sql)
        assert "LIMIT" in limited.upper()

    def test_existing_limit_preserved(self):
        sql = "SELECT * FROM orders LIMIT 10"
        limited = self.checker.add_limit(sql)
        assert "LIMIT 10" in limited


# ============================================================
# 4. SQL 查询执行测试
# ============================================================

class TestSQLExecution:
    """测试 SQL 执行（全流程）"""

    def test_simple_select(self, sample_db_url):
        """简单查询"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("SELECT COUNT(*) as cnt FROM orders")
        agent.close()

        assert result["success"] is True
        assert result["data"][0]["cnt"] == 10

    def test_aggregation_query(self, sample_db_url):
        """聚合查询：各产品线 GMV"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("""
            SELECT product_line, SUM(gmv) as total_gmv
            FROM orders
            GROUP BY product_line
            ORDER BY total_gmv DESC
        """)
        agent.close()

        assert result["success"] is True
        assert len(result["data"]) == 3
        assert result["columns"] == ["product_line", "total_gmv"]
        # C 产品线: 4200 + 2700 + 5500 = 12400
        c_row = next(r for r in result["data"] if r["product_line"] == "C")
        assert c_row["total_gmv"] == 12400.0

    def test_join_query(self, sample_db_url):
        """JOIN 查询：用户订单"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("""
            SELECT u.name, u.region, SUM(o.gmv) as total_gmv
            FROM orders o
            JOIN users u ON o.user_id = u.id
            GROUP BY u.name, u.region
            ORDER BY total_gmv DESC
        """)
        agent.close()

        assert result["success"] is True
        assert len(result["data"]) == 6
        assert "name" in result["columns"]
        assert "region" in result["columns"]

    def test_date_filter_query(self, sample_db_url):
        """日期过滤查询"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("""
            SELECT product_line, created_at, gmv
            FROM orders
            WHERE created_at >= '2026-04-10' AND created_at < '2026-04-20'
            ORDER BY created_at
        """)
        agent.close()

        assert result["success"] is True
        assert len(result["data"]) == 4

    def test_dangerous_sql_rejected(self, sample_db_url):
        """危险 SQL 被拒绝"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("DROP TABLE orders")
        agent.close()

        assert result["success"] is False
        assert result["error"] is not None

    def test_invalid_sql_returns_error(self, sample_db_url):
        """无效 SQL 返回错误"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("SELECT * FROM nonexistent_table")
        agent.close()

        assert result["success"] is False
        assert "error" in result["error"].lower() or "no such table" in result["error"].lower()

    def test_result_limit(self, sample_db_url):
        """结果集限制"""
        agent = SQLAgent(sample_db_url, max_retries=3)
        agent.security = SQLSecurityChecker(max_rows=3, timeout_seconds=30)
        result = agent.execute("SELECT * FROM orders")
        agent.close()

        assert result["success"] is True
        assert result["row_count"] <= 3


# ============================================================
# 5. 图表生成测试
# ============================================================

class TestChartGeneration:
    """测试图表生成"""

    def test_line_chart_for_time_series(self, sample_db_url):
        """时间序列数据 → 折线图"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("""
            SELECT created_at as dt, SUM(gmv) as daily_gmv
            FROM orders
            GROUP BY created_at
            ORDER BY created_at
        """)
        agent.close()

        gen = ChartGenerator()
        chart = gen.generate(result["data"], result["columns"], "每日 GMV 趋势", chart_type="line")

        assert chart["chart_type"] == "line"
        assert "echarts_option" in chart
        assert chart["echarts_option"].get("xAxis") is not None
        assert chart["echarts_option"].get("series") is not None
        assert len(chart["raw_data"]) > 0

    def test_bar_chart_for_categories(self, sample_db_url):
        """分类数据 → 柱状图"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("""
            SELECT region, COUNT(*) as user_count
            FROM users
            GROUP BY region
        """)
        agent.close()

        gen = ChartGenerator()
        chart = gen.generate(result["data"], result["columns"], "各区域用户数")

        assert chart["chart_type"] in ("bar", "pie")
        assert "echarts_option" in chart
        assert len(chart["raw_data"]) > 0

    def test_pie_chart_for_proportions(self, sample_db_url):
        """比例数据 → 饼图"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("""
            SELECT product_line, SUM(gmv) as total
            FROM orders
            GROUP BY product_line
        """)
        agent.close()

        gen = ChartGenerator()
        chart = gen.generate(result["data"], result["columns"], "产品线 GMV 占比", chart_type="pie")

        assert chart["chart_type"] == "pie"
        assert "series" in chart["echarts_option"]
        pie_data = chart["echarts_option"]["series"][0]["data"]
        assert len(pie_data) == 3

    def test_empty_data_returns_table(self):
        """空数据返回 table 类型"""
        gen = ChartGenerator()
        chart = gen.generate([], [], "空查询")

        assert chart["chart_type"] == "table"
        assert chart["data_summary"] == "无数据"

    def test_data_summary_generated(self, sample_db_url):
        """数据摘要包含统计信息"""
        agent = SQLAgent(sample_db_url)
        result = agent.execute("SELECT product_line, gmv FROM orders")
        agent.close()

        gen = ChartGenerator()
        chart = gen.generate(result["data"], result["columns"], "GMV 明细")

        assert "共 10 条记录" in chart["data_summary"]
        assert "gmv" in chart["data_summary"]


# ============================================================
# 6. 端到端完整流程测试
# ============================================================

class TestE2EFlow:
    """模拟完整用户流程"""

    def test_full_flow_create_to_chart(self, ds_store, sample_db_url):
        """完整流程：创建数据源 → 抓取 schema → 查询 → 生成图表"""
        # Step 1: 创建数据源
        ds = ds_store.create(
            tenant_id="demo",
            name="演示订单库",
            db_type="sqlite",
            connection_url=sample_db_url,
        )
        assert ds.id is not None

        # Step 2: 测试连接
        explorer = SchemaExplorer(ds.connection_url)
        success, msg = explorer.test_connection()
        assert success is True

        # Step 3: 抓取 Schema
        schema = explorer.explore()
        explorer.close()
        assert "orders" in schema["tables"]
        assert "users" in schema["tables"]

        # Step 4: 更新 schema_snapshot
        ds_store.update(ds.id, "demo", schema_snapshot=json.dumps(schema))
        updated_ds = ds_store.get(ds.id, "demo")
        assert updated_ds is not None
        stored_schema = updated_ds.schema_snapshot
        if isinstance(stored_schema, str):
            stored_schema = json.loads(stored_schema)
        assert "orders" in stored_schema["tables"]

        # Step 5: 用户标注 schema
        annotations = {
            "orders": {
                "description": "订单主表",
                "columns": {
                    "gmv": "成交总额（元）",
                    "product_line": "产品线编码",
                    "created_at": "下单日期",
                },
            }
        }
        ds_store.update(ds.id, "demo", schema_annotations=json.dumps(annotations))

        # Step 6: 执行业务查询
        agent = SQLAgent(ds.connection_url)
        result = agent.execute("""
            SELECT product_line, SUM(gmv) as total_gmv, COUNT(*) as order_count
            FROM orders
            GROUP BY product_line
            ORDER BY total_gmv DESC
        """)
        agent.close()

        assert result["success"] is True
        assert len(result["data"]) == 3

        # Step 7: 生成图表
        gen = ChartGenerator()
        chart = gen.generate(
            result["data"],
            result["columns"],
            "各产品线 GMV 和订单数",
            chart_type="bar",
        )

        assert chart["chart_type"] == "bar"
        assert chart["echarts_option"]["xAxis"]["data"] is not None
        assert len(chart["echarts_option"]["series"]) >= 1
        assert len(chart["raw_data"]) == 3

    def test_full_flow_trend_report(self, ds_store, sample_db_url):
        """完整流程：趋势报表"""
        ds = ds_store.create(
            tenant_id="demo",
            name="趋势分析库",
            db_type="sqlite",
            connection_url=sample_db_url,
        )

        agent = SQLAgent(ds.connection_url)
        result = agent.execute("""
            SELECT
                created_at as dt,
                product_line,
                gmv
            FROM orders
            ORDER BY created_at
        """)
        agent.close()
        assert result["success"] is True

        gen = ChartGenerator()
        chart = gen.generate(result["data"], result["columns"], "GMV 时间趋势")
        assert chart["chart_type"] == "line"
        assert "series" in chart["echarts_option"]


# ============================================================
# 7. SQL Agent 自我修正测试（Mock LLM）
# ============================================================

class TestSQLAgentRetry:
    """测试 SQL Agent 自我修正"""

    @pytest.mark.asyncio
    async def test_retry_fixes_bad_sql(self, sample_db_url):
        """LLM 修正错误 SQL"""
        from unittest.mock import AsyncMock, MagicMock
        from tars.models.base import ModelResponse

        mock_provider = MagicMock()
        fixed_response = ModelResponse(content="SELECT COUNT(*) as cnt FROM orders", model="test", usage=None)
        mock_provider.chat = AsyncMock(return_value=fixed_response)

        agent = SQLAgent(sample_db_url)
        result = await agent.execute_with_retry(
            sql="SELECT COUNT(*) FROM nonexistent_xyz",
            llm_provider=mock_provider,
            schema_context="tables: orders(id, user_id, product_line, gmv, created_at)",
            user_question="有多少订单？",
        )
        agent.close()

        assert result["success"] is True
        assert result["data"][0]["cnt"] == 10

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, sample_db_url):
        """重试耗尽仍失败"""
        from unittest.mock import AsyncMock, MagicMock
        from tars.models.base import ModelResponse

        mock_provider = MagicMock()
        bad_response = ModelResponse(content="SELECT * FROM still_wrong_table", model="test", usage=None)
        mock_provider.chat = AsyncMock(return_value=bad_response)

        agent = SQLAgent(sample_db_url, max_retries=2)
        result = await agent.execute_with_retry(
            sql="SELECT * FROM bad_table",
            llm_provider=mock_provider,
            schema_context="tables: orders",
            user_question="查询",
        )
        agent.close()

        assert result["success"] is False
