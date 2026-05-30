from typing import Any, Dict

from ..base import SubAgent, SubAgentType
from ._helpers import run_port_agent
from .prompts import YARD_PROMPT


class YardAgent(SubAgent):
    """堆场 Agent: 堆存分配。"""

    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.YARD, llm_provider)

    def get_system_prompt(self) -> str:
        return YARD_PROMPT

    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        return await run_port_agent(self, task, context, "堆场")
