# PortMeta Agent - SubAgent Manager
# 子代理管理器

import asyncio
from typing import Dict, Optional, Any
from .subagents.base import SubAgent, SubAgentType
from .subagents.code import CodeAgent
from .subagents.writing import WritingAgent
from .subagents.data import DataAgent
from .subagents.research import ResearchAgent
from .subagents.plan import PlanAgent
from .subagents.port import BerthAgent, YardAgent, VesselAgent


class SubAgentManager:
    """子代理管理器"""
    
    def __init__(self, master_agent=None):
        self.master_agent = master_agent
        self.subagents: Dict[SubAgentType, SubAgent] = {}
        self._delegation_weights: Dict[str, float] = {}
        self._load_subagents()
    
    def _load_subagents(self):
        """加载所有子代理"""
        self.subagents[SubAgentType.CODE] = CodeAgent()
        self.subagents[SubAgentType.WRITING] = WritingAgent()
        self.subagents[SubAgentType.DATA] = DataAgent()
        self.subagents[SubAgentType.RESEARCH] = ResearchAgent()
        self.subagents[SubAgentType.PLAN] = PlanAgent()
        self.subagents[SubAgentType.BERTH] = BerthAgent()
        self.subagents[SubAgentType.YARD] = YardAgent()
        self.subagents[SubAgentType.VESSEL] = VesselAgent()

    def apply_tenant_overrides(self, tenant_id: str = "default") -> None:
        """Merge evolution subagents.json overrides for a tenant."""
        import json
        from pathlib import Path

        path = Path.home() / ".tars" / "agents" / tenant_id / "subagents.json"
        if not path.exists():
            return
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(config, dict):
            return
        delegation_weights = config.get("delegation_weights")
        if isinstance(delegation_weights, dict):
            self._delegation_weights = {
                str(k): float(v) for k, v in delegation_weights.items()
            }
        for agent_type, cfg in config.items():
            if agent_type in ("delegation_weights", "personality_weights"):
                continue
            if isinstance(cfg, dict):
                self.update_subagent_config(str(agent_type), cfg)
    
    def get_subagent(self, agent_type: SubAgentType) -> Optional[SubAgent]:
        """获取子代理"""
        return self.subagents.get(agent_type)
    
    def get_all_subagents(self) -> Dict[str, dict]:
        """获取所有子代理信息"""
        return {
            agent_type.value: subagent.get_info()
            for agent_type, subagent in self.subagents.items()
        }
    
    def update_subagent_config(self, agent_type: str, config: dict):
        """更新子代理配置"""
        try:
            agent_type_enum = SubAgentType(agent_type)
            agent = self.subagents.get(agent_type_enum)
            if agent:
                agent.update_config(config)
                return True
            return False
        except ValueError:
            return False
    
    def _determine_agent_type(self, task: str) -> Optional[SubAgentType]:
        """
        根据任务内容确定合适的子代理类型
        
        Args:
            task: 用户任务描述
        
        Returns:
            Optional[SubAgentType]: 子代理类型，如果无法确定则返回None
        """
        task_lower = task.lower()

        port_keyword_map = {
            SubAgentType.BERTH: ["靠泊", "泊位", "berth", "靠"],
            SubAgentType.YARD: ["堆场", "堆存", "箱位", "yard", "卸货", "装箱"],
            SubAgentType.VESSEL: ["船务", "航次", "eta", "vessel", "船舶", "吃水"],
        }
        port_scores: Dict[SubAgentType, float] = {}
        for agent_type, keywords in port_keyword_map.items():
            hits = sum(1 for keyword in keywords if keyword in task_lower)
            if hits > 0:
                weight = self._delegation_weights.get(agent_type.value, 1.0)
                port_scores[agent_type] = hits * float(weight)
        if port_scores:
            return max(port_scores, key=port_scores.get)

        code_keywords = ["代码", "编程", "python", "javascript", "typescript",
                         "code", "function", "class", "bug", "debug", "error"]
        writing_keywords = ["写", "文章", "文案", "报告", "写作", "邮件", 
                            "letter", "essay", "article", "story"]
        data_keywords = ["数据", "分析", "图表", "统计", "excel", "csv", 
                         "data", "chart", "graph", "analysis"]
        research_keywords = ["搜索", "研究", "查找", "资料", "调研", 
                            "research", "search", "information"]
        plan_keywords = ["计划", "规划", "任务", "步骤",
                         "plan", "schedule", "task", "goal"]

        keyword_map = {
            SubAgentType.CODE: code_keywords,
            SubAgentType.WRITING: writing_keywords,
            SubAgentType.DATA: data_keywords,
            SubAgentType.RESEARCH: research_keywords,
            SubAgentType.PLAN: plan_keywords,
        }
        scores: Dict[SubAgentType, float] = {}
        for agent_type, keywords in keyword_map.items():
            hits = sum(1 for keyword in keywords if keyword in task_lower)
            if hits > 0:
                weight = self._delegation_weights.get(agent_type.value, 1.0)
                scores[agent_type] = hits * float(weight)

        if not scores:
            return None
        return max(scores, key=scores.get)
    
    async def delegate_task(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        委派任务给合适的子代理

        Args:
            task: 任务描述
            context: 上下文信息（包含人格、会话等）

        Returns:
            str: 任务执行结果
        """
        agent_type = self._determine_agent_type(task)

        if agent_type is None:
            return await self._handle_direct(task, context)

        tenant_id = (context or {}).get("tenant_id", "default")
        self.apply_tenant_overrides(tenant_id)

        agent = self.subagents.get(agent_type)
        if not agent or not agent.config.enabled:
            return await self._handle_direct(task, context)

        # 使用主代理的 provider
        if self.master_agent and self.master_agent.provider:
            agent.llm_provider = self.master_agent.provider

        return await agent.execute(task, context)
    
    async def _handle_direct(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        直接处理任务（当没有合适的子代理时）
        
        Args:
            task: 任务描述
            context: 上下文信息
        
        Returns:
            str: 处理结果
        """
        if self.master_agent and hasattr(self.master_agent, '_direct_llm_call'):
            return await self.master_agent._direct_llm_call(task)
        else:
            return f"直接处理任务...\n任务: {task}"
    
    async def invoke_subagent(self, agent_type: str, task: str, context: Dict[str, Any] = None) -> str:
        """
        直接调用指定的子代理

        Args:
            agent_type: 子代理类型
            task: 任务描述
            context: 上下文信息

        Returns:
            str: 任务执行结果
        """
        try:
            agent_type_enum = SubAgentType(agent_type)
            tenant_id = (context or {}).get("tenant_id", "default")
            self.apply_tenant_overrides(tenant_id)
            agent = self.subagents.get(agent_type_enum)

            if not agent:
                return f"未知的子代理类型: {agent_type}"

            if not agent.config.enabled:
                return f"子代理 {agent_type} 已被禁用"

            # 使用主代理的 provider
            if self.master_agent and self.master_agent.provider:
                agent.llm_provider = self.master_agent.provider

            return await agent.execute(task, context)
        except ValueError:
            return f"无效的子代理类型: {agent_type}"
    
    async def run_parallel_tasks(
        self,
        tasks: list,
        context: Dict[str, Any] = None,
        orch_mem=None,
        task_id: str = None,
    ) -> dict:
        """
        并行执行多个任务
        
        Args:
            tasks: 任务列表，每个任务包含 agent_type 和 task
            context: 上下文信息
            orch_mem: 可选 OrchestrationMemory，传入时落库子任务产出
            task_id: 编排任务 ID，与 orch_mem 配合使用
        
        Returns:
            dict: 任务执行结果字典
        """
        async def run_task(task_info):
            agent_type = task_info.get("agent_type")
            subtask = task_info.get("task", "")
            task_context = context
            if task_info.get("context"):
                task_context = {**(context or {}), **task_info["context"]}
            if orch_mem and task_id:
                task_context = {**(task_context or {}), "shared": orch_mem.get_shared(task_id)}
            result = await self.invoke_subagent(agent_type, subtask, task_context)
            if orch_mem and task_id:
                orch_mem.record_output(task_id, agent_type=agent_type, subtask=subtask, output=result)
            return (agent_type, result)
        
        results = await asyncio.gather(*[run_task(task) for task in tasks])
        return dict(results)

    async def run_phased_tasks(
        self,
        tasks: list,
        context: Dict[str, Any] = None,
        orch_mem=None,
        task_id: str = None,
    ) -> dict:
        """先并行 phase=parallel，再串行 phase=serial（如堆场依赖泊位黑板）。"""
        parallel = [t for t in tasks if t.get("phase", "parallel") != "serial"]
        serial = [t for t in tasks if t.get("phase") == "serial"]
        results: Dict[str, str] = {}
        if parallel:
            results.update(await self.run_parallel_tasks(parallel, context, orch_mem, task_id))
        if serial:
            results.update(await self.run_parallel_tasks(serial, context, orch_mem, task_id))
        return results
    
    def get_available_models(self) -> list:
        """获取可用的模型列表"""
        if self.master_agent and hasattr(self.master_agent, 'provider'):
            return self.master_agent.provider.get_available_models()
        return []
    
    def set_llm_provider(self, agent_type: SubAgentType, llm_provider):
        """为子代理设置LLM提供者"""
        agent = self.subagents.get(agent_type)
        if agent:
            agent.llm_provider = llm_provider
