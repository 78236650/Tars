"""
TARS Agent Self-Evolution Module
自进化模块 - 让 TARS 能够自我学习和优化
"""

from .evaluator import ResponseEvaluator, EvaluationResult
from .optimizer import PersonalityOptimizer, SubAgentOptimizer
from .prompt_tuner import PromptTuner
from .manager import EvolutionManager

__all__ = [
    "ResponseEvaluator",
    "EvaluationResult",
    "PersonalityOptimizer",
    "SubAgentOptimizer",
    "PromptTuner",
    "EvolutionManager",
]
