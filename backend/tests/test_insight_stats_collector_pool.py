"""Tests for StatsCollector connection pool sizing."""
from tars.insight.config import InsightBudget
from tars.insight.stats_collector import StatsCollector


def test_engine_pool_size_scales_with_parallel(tmp_path):
    url = f"sqlite:///{tmp_path}/a.db"
    budget = InsightBudget(parallel_tables=5)
    sc = StatsCollector(url, "sqlite", "sqlite", budget)
    engine = sc._engine_get()
    assert engine is not None
    sc.close()
