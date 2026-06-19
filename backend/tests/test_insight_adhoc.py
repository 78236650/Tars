"""InsightForge adhoc NL→SQL 测试。"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from tars.insight.metric_qa_engine import MetricQaEngine, InsightQaError


class FakeLLM:
    """模拟 LLM provider 返回固定 SQL。"""
    def __init__(self, sql: str = "SELECT COUNT(*) FROM orders"):
        self._sql = sql

    async def complete(self, prompt: str, max_tokens: int = 800):
        resp = MagicMock()
        resp.content = self._sql
        return resp


@pytest.fixture
def engine_with_llm(test_db):
    return MetricQaEngine(test_db, llm_provider=FakeLLM())


@pytest.fixture
def engine_no_llm(test_db):
    return MetricQaEngine(test_db)  # no llm_provider


# ── _build_adhoc_sql ───────────────────────────────────────

async def test_build_adhoc_sql_basic(engine_with_llm, test_db):
    schema = {
        "tables": {
            "orders": {
                "columns": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "amount", "type": "REAL"},
                    {"name": "created_at", "type": "TEXT"},
                ],
                "primary_key": ["id"],
            }
        }
    }
    sql = await engine_with_llm._build_adhoc_sql(
        question="总订单数",
        schema_snapshot=schema,
        db_type="sqlite",
    )
    assert "SELECT" in sql


async def test_build_adhoc_no_schema_raises(engine_with_llm, test_db):
    with pytest.raises(InsightQaError, match="缺少 Schema"):
        await engine_with_llm._build_adhoc_sql(
            question="随便问",
            schema_snapshot={"tables": {}},
            db_type="sqlite",
        )


async def test_build_adhoc_no_llm_raises(engine_no_llm, test_db):
    schema = {
        "tables": {
            "t": {"columns": [{"name": "x", "type": "INTEGER"}]}
        }
    }
    with pytest.raises(InsightQaError, match="无可用 LLM"):
        await engine_no_llm._build_adhoc_sql(
            question="问",
            schema_snapshot=schema,
            db_type="sqlite",
        )


# ── _extract_sql ────────────────────────────────────────────

def test_extract_sql_plain():
    assert MetricQaEngine._extract_sql("SELECT 1") == "SELECT 1"


def test_extract_sql_markdown_wrapped():
    text = "```sql\nSELECT * FROM t\n```"
    assert MetricQaEngine._extract_sql(text) == "SELECT * FROM t"


def test_extract_sql_with_explanation():
    text = "这是查询：\nSELECT COUNT(*) FROM t\n返回总数"
    result = MetricQaEngine._extract_sql(text)
    assert "SELECT COUNT(*) FROM t" in result


def test_extract_sql_strips_semicolon():
    assert MetricQaEngine._extract_sql("SELECT 1;") == "SELECT 1"


# ── adhoc 流程贯通 ──────────────────────────────────────────

async def test_adhoc_miss_falls_through_to_generation(engine_with_llm, test_db):
    """验证 adhoc 分支不再提前返回错误，而是执行 LLM 生成 SQL"""
    from tars.insight.metric_answer import MetricAnswer

    # 需要有一个 datasource_id 存在（否则 ask 会抛错）
    # 所以改用 _resolve_sql 直接测
    sql, metric, tier = await engine_with_llm._resolve_sql(
        datasource_id="ds1",
        tenant_id="org_default",
        connection_url="sqlite:///:memory:",
        db_type="sqlite",
        question="总行数",
        decision=MagicMock(branch="miss"),
        metrics=[],
        as_of_date=None,
        schema_snapshot={
            "tables": {
                "t": {"columns": [{"name": "id", "type": "INTEGER"}]}
            }
        },
    )
    assert "SELECT" in sql
    assert metric is None  # adhoc 无预定义指标
    assert tier == "adhoc"
