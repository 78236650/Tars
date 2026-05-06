"""
Parameter Optimizer - 自动优化人格参数和子代理配置
"""
import random
import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from .evaluator import EvaluationResult, ConversationRecord


@dataclass
class OptimizationStep:
    """优化步骤记录"""
    parameter_name: str
    old_value: float
    new_value: float
    expected_improvement: float
    actual_improvement: Optional[float]
    timestamp: datetime


class PersonalityOptimizer:
    """人格参数优化器（使用 Bayesian 风格优化算法）"""
    
    def __init__(self, learning_rate: float = 0.05, exploration_rate: float = 0.2):
        self.learning_rate = learning_rate
        self.exploration_rate = exploration_rate
        self.history: List[OptimizationStep] = []
        self.parameter_importance = {
            'honesty': 0.15,
            'humor': 0.10,
            'initiative': 0.15,
            'empathy': 0.15,
            'formality': 0.10,
            'creativity': 0.10,
            'conciseness': 0.10,
            'technical_depth': 0.05,
            'curiosity': 0.05,
            'skepticism': 0.05
        }
        
    def optimize(self, current_params: Dict[str, float], 
                history_records: List[ConversationRecord]) -> Dict[str, float]:
        """
        基于反馈历史优化人格参数
        
        Args:
            current_params: 当前参数
            history_records: 历史对话记录
            
        Returns:
            优化后的参数
        """
        optimized_params = current_params.copy()
        
        if len(history_records) < 10:
            return optimized_params
        
        # 分析每个参数与评分的关系
        for param_name in current_params:
            correlation = self._calculate_parameter_correlation(param_name, history_records)
            
            if random.random() < self.exploration_rate:
                change = (random.random() - 0.5) * 0.1
            else:
                change = correlation * self.learning_rate
            
            old_value = optimized_params[param_name]
            new_value = max(0.0, min(1.0, old_value + change))
            
            optimized_params[param_name] = new_value
            
            step = OptimizationStep(
                parameter_name=param_name,
                old_value=old_value,
                new_value=new_value,
                expected_improvement=abs(change),
                actual_improvement=None,
                timestamp=datetime.now()
            )
            self.history.append(step)
        
        return optimized_params
    
    def _calculate_parameter_correlation(self, param_name: str, 
                                    history_records: List[ConversationRecord]) -> float:
        """计算参数与评分的相关性"""
        
        high_score_changes = []
        
        for record in history_records:
            if not record.evaluation:
                continue
                continue
            
            params = record.context.get('personality_params', {})
            if param_name not in params:
                continue
            
            param_value = params[param_name]
            score = record.evaluation.overall_score
            
            score_changes.append((param_value, score))
        
        if len(score_changes) < 5:
            return 0.0
        
        avg_high = sum(s for v, s in score_changes if v > 0.5)
        avg_low = sum(s for v, s in score_changes if v <= 0.5)
        
        if not avg_high or not avg_low:
            return 0.0
        
        return (avg_high - avg_low) if avg_high > avg_low else -(avg_low - avg_high)
    
    def update_feedback(self, improvement: float):
        """更新最后一次优化的反馈"""
        if not self.history:
            return
        self.history[-1].actual_improvement = improvement


class SubAgentOptimizer:
    """子代理配置优化器"""
    
    def __init__(self):
        self.usage_stats: Dict[str, int] = {}
        self.performance_history: Dict[str, List[float]] = {}
        
    def optimize_task_delegation(self, task_history: List[ConversationRecord]) -> Dict[str, float]:
        """优化任务委派策略"""
        
        for record in task_history:
            if record.subagent_used:
                sa = record.subagent_used
                self.usage_stats[sa] = self.usage_stats.get(sa, 0) + 1
                
                if record.evaluation:
                    if sa not in self.performance_history:
                        self.performance_history[sa] = []
                    self.performance_history[sa].append(record.evaluation.overall_score)
        
        total_usage = sum(self.usage_stats.values()) or 1
        delegation_weights = {}
        for agent_type, count in self.usage_stats.items():
            base_weight = count / total_usage
            performance = self._get_performance_score(agent_type)
            delegation_weights[agent_type] = base_weight * (0.5 + 0.5 * performance)
        
        total = sum(delegation_weights.values()) or 1
        return {k: v / total for k, v in delegation_weights.items()}
    
    def _get_performance_score(self, agent_type: str) -> float:
        """获取子代理的性能评分"""
        if agent_type not in self.performance_history:
            return 0.7
        scores = self.performance_history[agent_type]
        return sum(scores) / len(scores)
    
    def optimize_personality_weights(self, feedback_history: List[ConversationRecord]) -> Dict[str, float]:
        """优化子代理的人格融合权重"""
        
        optimal_weights = {}
        
        for record in feedback_history:
            if record.subagent_used and record.evaluation:
                agent_type = record.subagent_used
                score = record.evaluation.style_match
                
                if agent_type not in optimal_weights:
                    optimal_weights[agent_type] = []
                optimal_weights[agent_type].append(score)
        
        final_weights = {}
        for agent_type, scores in optimal_weights.items():
            avg = sum(scores) / len(scores)
            final_weights[agent_type] = max(0.0, min(1.0, 0.3 + 0.7 * avg))
        
        return final_weights
    
    def get_recommendations(self) -> Dict[str, Any]:
        """获取子代理优化建议"""
        
        recommendations = {}
        
        for agent_type in self.usage_stats:
            performance = self._get_performance_score(agent_type)
            usage = self.usage_stats.get(agent_type, 0)
            
            recommendations[agent_type] = {
                'usage_count': usage,
                'performance_score': performance,
                'recommendation': 'keep' if performance > 0.6 else 'review'
            }
        
        return recommendations
