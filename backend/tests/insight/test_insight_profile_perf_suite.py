"""Parametrized runner for tests/insight/profile_perf_suite.yaml (INS-2.1).

Cases skip until the corresponding INS-2.1 module lands — see profile_perf_runner.py.
"""
from __future__ import annotations

import pytest

from tests.insight.profile_perf_runner import load_perf_cases, run_integration_case, run_unit_case

_UNIT = load_perf_cases(layers=["unit"])
_INTEGRATION = load_perf_cases(layers=["integration"])
_BENCH = load_perf_cases(layers=["bench"])


@pytest.mark.parametrize("case", _UNIT, ids=lambda c: c["id"])
def test_profile_perf_suite_unit(case, tmp_path):
    run_unit_case(case, tmp_path)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("case", _INTEGRATION, ids=lambda c: c["id"])
async def test_profile_perf_suite_integration(case, tmp_path):
    await run_integration_case(case, tmp_path)


@pytest.mark.insight_perf
@pytest.mark.parametrize("case", _BENCH, ids=lambda c: c["id"])
def test_profile_perf_suite_bench(case, tmp_path):
    import os

    if os.environ.get("INSIGHT_PERF_BENCH") != "1":
        pytest.skip("set INSIGHT_PERF_BENCH=1")
    from tests.insight.profile_perf_runner import run_bench_case

    run_bench_case(case, tmp_path)
