from typing import Any, Dict

from ..base import SubAgent, SubAgentType
from ._helpers import run_port_agent
from .prompts import VESSEL_PROMPT


class VesselAgent(SubAgent):
    """船务 Agent: 船舶动态。"""

    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.VESSEL, llm_provider)

    def get_system_prompt(self) -> str:
        return VESSEL_PROMPT

    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        return await run_port_agent(self, task, context, "船务")
