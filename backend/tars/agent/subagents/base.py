# PortMeta Agent - SubAgent Base
# 子代理抽象基类

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass


class SubAgentType(Enum):
    """子代理类型枚举"""
    CODE = "code"
    WRITING = "writing"
    DATA = "data"
    RESEARCH = "research"
    PLAN = "plan"
    # v4.4.0 港航
    BERTH = "berth"
    YARD = "yard"
    VESSEL = "vessel"
    CRANE = "crane"
    CARGO = "cargo"
    REPORT = "report"


@dataclass
class SubAgentConfig:
    """子代理配置"""
    type: SubAgentType
    name: str
    description: str
    llm_model: Optional[str] = None
    llm_provider: Optional[str] = None
    temperature: float = 0.7
    personality_weight: float = 0.5
    enabled: bool = True


class SubAgent(ABC):
    """子代理抽象基类"""
    
    def __init__(self, agent_type: SubAgentType, llm_provider=None):
        self.type = agent_type
        self.llm_provider = llm_provider
        self.personality_weight = 0.5
        self.config = self._get_default_config()
    
    def _get_default_config(self) -> SubAgentConfig:
        """获取默认配置"""
        configs = {
            SubAgentType.CODE: SubAgentConfig(
                type=SubAgentType.CODE,
                name="代码助手",
                description="专业的代码编写和调试助手",
                llm_model=None,
                temperature=0.2,
                personality_weight=0.3
            ),
            SubAgentType.WRITING: SubAgentConfig(
                type=SubAgentType.WRITING,
                name="写作助手",
                description="创意写作和文案编辑助手",
                llm_model=None,
                temperature=0.7,
                personality_weight=0.7
            ),
            SubAgentType.DATA: SubAgentConfig(
                type=SubAgentType.DATA,
                name="数据分析助手",
                description="数据处理和可视化专家",
                llm_model=None,
                temperature=0.3,
                personality_weight=0.5
            ),
            SubAgentType.RESEARCH: SubAgentConfig(
                type=SubAgentType.RESEARCH,
                name="研究助手",
                description="信息检索和知识汇总专家",
                llm_model=None,
                temperature=0.5,
                personality_weight=0.4
            ),
            SubAgentType.PLAN: SubAgentConfig(
                type=SubAgentType.PLAN,
                name="规划助手",
                description="计划制定和任务分解专家",
                llm_model=None,
                temperature=0.6,
                personality_weight=0.5
            ),
            SubAgentType.BERTH: SubAgentConfig(
                type=SubAgentType.BERTH,
                name="泊位调度",
                description="靠泊计划与泊位选择",
                llm_model=None,
                temperature=0.3,
                personality_weight=0.3,
            ),
            SubAgentType.YARD: SubAgentConfig(
                type=SubAgentType.YARD,
                name="堆场调度",
                description="堆场箱位分配与利用率优化",
                llm_model=None,
                temperature=0.3,
                personality_weight=0.3,
            ),
            SubAgentType.VESSEL: SubAgentConfig(
                type=SubAgentType.VESSEL,
                name="船务动态",
                description="船舶/航次 ETA 与参数确认",
                llm_model=None,
                temperature=0.3,
                personality_weight=0.3,
            ),
            SubAgentType.CRANE: SubAgentConfig(
                type=SubAgentType.CRANE,
                name="岸桥作业",
                description="岸桥派工与作业序列",
                llm_model=None,
                temperature=0.3,
                personality_weight=0.3,
                enabled=False,
            ),
            SubAgentType.CARGO: SubAgentConfig(
                type=SubAgentType.CARGO,
                name="货代单证",
                description="货主需求与单证齐套",
                llm_model=None,
                temperature=0.3,
                personality_weight=0.3,
                enabled=False,
            ),
            SubAgentType.REPORT: SubAgentConfig(
                type=SubAgentType.REPORT,
                name="作业报表",
                description="航次/日报汇总",
                llm_model=None,
                temperature=0.3,
                personality_weight=0.3,
                enabled=False,
            ),
        }
        return configs.get(self.type, SubAgentConfig(type=self.type, name="未知", description=""))
    
    @abstractmethod
    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        """
        执行任务
        
        Args:
            task: 任务描述
            context: 上下文信息
        
        Returns:
            str: 任务执行结果
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取子代理的专业提示词
        
        Returns:
            str: 系统提示词
        """
        pass
    
    def merge_with_personality(self, personality) -> str:
        """
        融合人格提示词
        
        Args:
            personality: 主代理人格对象
        
        Returns:
            str: 融合后的提示词
        """
        if not personality:
            return self.get_system_prompt()
        
        base_prompt = self.get_system_prompt()
        
        if hasattr(personality, 'parameters'):
            params = vars(personality.parameters)
            personality_str = "\n".join([
                f"- {key}: {value}" 
                for key, value in params.items()
            ])
        else:
            personality_str = ""
        
        behavior_rules = []
        if hasattr(personality, 'behavior_rules'):
            behavior_rules = personality.behavior_rules
        
        rules_str = "\n".join(behavior_rules) if behavior_rules else ""
        
        return f"""{base_prompt}

## 人格特质（权重: {self.personality_weight}）
{personality_str}

## 行为规则
{rules_str}

## 人格融合规则
- 你的回答风格应该是人格特质和专业领域的结合
- 人格权重决定了人格特质的影响程度
- 当权重为0时，完全遵循专业领域指令
- 当权重为1时，完全遵循人格特质
"""
    
    def update_config(self, config: dict):
        """
        更新配置
        
        Args:
            config: 配置字典
        """
        if 'temperature' in config:
            self.config.temperature = config['temperature']
        if 'personality_weight' in config:
            self.personality_weight = config['personality_weight']
        if 'llm_model' in config:
            self.config.llm_model = config['llm_model']
        if 'llm_provider' in config:
            self.config.llm_provider = config['llm_provider']
        if 'enabled' in config:
            self.config.enabled = config['enabled']
    
    def get_info(self) -> dict:
        """获取子代理信息"""
        return {
            'type': self.type.value,
            'name': self.config.name,
            'description': self.config.description,
            'enabled': self.config.enabled,
            'llm_model': self.config.llm_model,
            'llm_provider': self.config.llm_provider,
            'temperature': self.config.temperature,
            'personality_weight': self.personality_weight,
        }
