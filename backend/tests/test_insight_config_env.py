"""InsightForge profile config env override tests (INS-2.1)."""
import os

import tars.insight.config as insight_config
from tars.insight.config import InsightBudget, load_insight_config


def _reload_config(monkeypatch, **env):
    for key, val in env.items():
        if val is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, val)
    insight_config._insight_config = None


def test_parallel_tables_env_override(monkeypatch):
    _reload_config(monkeypatch, TARS_INSIGHT_PARALLEL_TABLES="6", TARS_INSIGHT_INCREMENTAL=None)
    cfg = load_insight_config()
    assert cfg.profile.parallel_tables == 6


def test_incremental_disabled_env_override(monkeypatch):
    _reload_config(monkeypatch, TARS_INSIGHT_INCREMENTAL="0", TARS_INSIGHT_PARALLEL_TABLES=None)
    cfg = load_insight_config()
    assert cfg.profile.enable_incremental is False


def test_apply_profile_env_overrides_direct():
    budget = InsightBudget(parallel_tables=3, enable_incremental=True)
    os.environ["TARS_INSIGHT_PARALLEL_TABLES"] = "2"
    os.environ["TARS_INSIGHT_INCREMENTAL"] = "0"
    try:
        from tars.insight.config import _apply_profile_env_overrides

        out = _apply_profile_env_overrides(budget)
        assert out.parallel_tables == 2
        assert out.enable_incremental is False
    finally:
        os.environ.pop("TARS_INSIGHT_PARALLEL_TABLES", None)
        os.environ.pop("TARS_INSIGHT_INCREMENTAL", None)
