"""Task 7: Agent 拆分前的 smoke test。"""

from tars.agent.agent import AgentV2


def test_agent_instantiates():
    """AgentV2 可在无参数情况下实例化。"""
    a = AgentV2()
    assert a is not None
    assert a.db is not None
