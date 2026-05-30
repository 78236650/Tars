"""港航专家 Agent 单测."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.agent.subagents.port.berth import BerthAgent
from tars.agent.subagents.port.yard import YardAgent
from tars.agent.subagents.port.vessel import VesselAgent
from tars.agent.subagents.port._helpers import build_user_content
from tars.agent.subagent_manager import SubAgentManager
from tars.agent.subagents.base import SubAgentType


def test_berth_agent_prompt():
    agent = BerthAgent()
    prompt = agent.get_system_prompt()
    assert "泊位" in prompt and "水深" in prompt


def test_yard_agent_prompt():
    agent = YardAgent()
    assert "堆场" in agent.get_system_prompt()


def test_vessel_agent_prompt():
    agent = VesselAgent()
    assert "航次" in agent.get_system_prompt() or "船舶" in agent.get_system_prompt()


def test_build_user_content_includes_shared():
    text = build_user_content("选泊位", {"shared": {"berth": {"recommendation": "3号"}}})
    assert "协作黑板" in text
    assert "3号" in text


@pytest.mark.asyncio
async def test_berth_execute_without_llm():
    agent = BerthAgent()
    out = await agent.execute("为 COSCO123 选泊位", {"domain_memory": "test"})
    assert "[泊位]" in out


def test_port_routing_priority():
    mgr = SubAgentManager()
    assert mgr._determine_agent_type("安排 COSCO123 靠3号泊位卸货") == SubAgentType.BERTH
    assert mgr._determine_agent_type("分配堆场箱位") == SubAgentType.YARD
    assert mgr._determine_agent_type("确认航次 ETA") == SubAgentType.VESSEL


@pytest.mark.asyncio
async def test_berth_execute_with_mock_llm():
    agent = BerthAgent()
    mock = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = "推荐3号泊位，水深16m满足"
    mock.chat = AsyncMock(return_value=mock_resp)
    agent.llm_provider = mock
    out = await agent.execute("选泊位", {"shared": {}})
    assert "3号泊位" in out
    mock.chat.assert_called_once()
