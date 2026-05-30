from typing import Any, Dict

from ..base import SubAgent, SubAgentType
from ._helpers import run_port_agent
from .prompts import BERTH_PROMPT


class BerthAgent(SubAgent):
    """泊位 Agent: 靠泊计划决策。"""

    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.BERTH, llm_provider)

    def get_system_prompt(self) -> str:
        return BERTH_PROMPT

    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        return await run_port_agent(self, task, context, "泊位")
