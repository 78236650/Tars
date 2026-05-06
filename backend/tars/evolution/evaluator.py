"""
Response Evaluator - 评估对话效果的质量
"""
import re
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class FeedbackType(Enum):
    EXPLICIT = "explicit"  # 用户显式评分/反馈
    IMPLICIT = "implicit"  # 隐式反馈（用户行为）


@dataclass
class EvaluationResult:
    """评估结果"""
    overall_score: float  # 总分 0-1
    relevance: float  # 相关性 0-1
    completeness: float  # 完整性 0-1
    accuracy: float  # 准确性 0-1
    style_match: float  # 风格匹配度 0-1
    tool_efficiency: float  # 工具使用效率 0-1
    feedback_type: FeedbackType
    user_feedback: Optional[str] = None
    implicit_signals: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationRecord:
    """对话记录"""
    conversation_id: str
    query: str
    response: str
    timestamp: datetime
    evaluation: Optional[EvaluationResult] = None
    context: Dict[str, Any] = field(default_factory=dict)
    tools_used: List[str] = field(default_factory=list)
    subagent_used: Optional[str] = None


class ResponseEvaluator:
    """响应评估器"""
    
    def __init__(self):
        self.history: List[ConversationRecord] = []
        
        # 评估关键词库
        self.positive_keywords = [
            "完美", "很好", "太棒了", "感谢", "谢谢", "有帮助", "有用",
            "perfect", "great", "excellent", "thanks", "helpful", "good",
            "clear", "well", "exactly", "right", "correct"
        ]
        self.negative_keywords = [
            "不对", "错误", "不完整", "不清楚", "没用", "不好",
            "wrong", "incorrect", "incomplete", "unclear", "useless", "bad",
            "confusing", "not", "no", "incorrect", "false"
        ]
        
    def evaluate(self, query: str, response: str, context: Dict[str, Any] = None, 
                explicit_feedback: Optional[str] = None) -> EvaluationResult:
        """
        评估响应质量
        
        Args:
            query: 用户查询
            response: Agent 响应
            context: 上下文信息
            explicit_feedback: 用户显式反馈
            
        Returns:
            EvaluationResult: 评估结果
        """
        if explicit_feedback:
            return self._evaluate_with_feedback(query, response, context, explicit_feedback)
        else:
            return self._evaluate_implicitly(query, response, context)
    
    def _evaluate_with_feedback(self, query: str, response: str, context: Dict[str, Any],
                              explicit_feedback: str) -> EvaluationResult:
        """基于用户显式反馈评估"""
        # 解析评分（支持数字评分或文字反馈）
        score = self._parse_feedback_score(explicit_feedback)
        
        # 提取各项指标
        relevance = self._assess_relevance(query, response)
        completeness = self._assess_completeness(response)
        accuracy = self._assess_accuracy(response, explicit_feedback)
        style_match = self._assess_style_match(response, context)
        tool_efficiency = self._assess_tool_efficiency(context)
        
        # 综合得分
        overall_score = (relevance * 0.3 + completeness * 0.2 + 
                        accuracy * 0.3 + style_match * 0.1 + 
                        tool_efficiency * 0.1)
        
        # 但显式反馈有更高权重
        overall_score = overall_score * 0.3 + score * 0.7
        
        return EvaluationResult(
            overall_score=overall_score,
            relevance=relevance,
            completeness=completeness,
            accuracy=accuracy,
            style_match=style_match,
            tool_efficiency=tool_efficiency,
            feedback_type=FeedbackType.EXPLICIT,
            user_feedback=explicit_feedback,
            created_at=datetime.now()
        )
    
    def _evaluate_implicitly(self, query: str, response: str, 
                           context: Dict[str, Any] = None) -> EvaluationResult:
        """隐式评估（基于响应内容分析）"""
        context = context or {}
        
        relevance = self._assess_relevance(query, response)
        completeness = self._assess_completeness(response)
        accuracy = self._assess_accuracy_implicit(response)
        style_match = self._assess_style_match(response, context)
        tool_efficiency = self._assess_tool_efficiency(context)
        
        # 综合得分
        overall_score = (relevance * 0.3 + completeness * 0.25 + 
                        accuracy * 0.25 + style_match * 0.1 + 
                        tool_efficiency * 0.1)
        
        # 检测隐式反馈信号
        implicit_signals = self._detect_implicit_signals(query, response)
        
        return EvaluationResult(
            overall_score=overall_score,
            relevance=relevance,
            completeness=completeness,
            accuracy=accuracy,
            style_match=style_match,
            tool_efficiency=tool_efficiency,
            feedback_type=FeedbackType.IMPLICIT,
            implicit_signals=implicit_signals,
            created_at=datetime.now()
        )
    
    def _parse_feedback_score(self, feedback: str) -> float:
        """解析用户反馈，返回 0-1 的评分"""
        # 检查是否有数字评分
        number_match = re.search(r'(\d+(\.\d+)?)/?(\d*)', feedback)
        if number_match:
            score = float(number_match.group(1))
            max_score = float(number_match.group(3)) if number_match.group(3) else 10.0
            return min(1.0, max(0.0, score / max_score))
        
        # 基于关键词评分
        positive_count = sum(1 for kw in self.positive_keywords if kw in feedback.lower())
        negative_count = sum(1 for kw in self.negative_keywords if kw in feedback.lower())
        
        if positive_count > negative_count:
            return 0.7 + (positive_count * 0.05)
        elif negative_count > positive_count:
            return max(0.0, 0.3 - (negative_count * 0.05))
        else:
            return 0.5  # 中性反馈
    
    def _assess_relevance(self, query: str, response: str) -> float:
        """评估响应相关性"""
        query_words = set(re.findall(r'\w+', query.lower()))
        response_words = set(re.findall(r'\w+', response.lower()))
        
        if not query_words:
            return 0.5
        
        # 计算词重合度
        overlap = len(query_words.intersection(response_words))
        jaccard = overlap / len(query_words.union(response_words))
        
        # 简单启发式评估
        return min(1.0, 0.3 + jaccard * 0.7)
    
    def _assess_completeness(self, response: str) -> float:
        """评估响应完整性"""
        # 启发式：长度、结构完整性
        if len(response) < 20:
            return 0.3
        
        # 检查是否有完整的句子结构
        sentence_endings = ['.', '!', '?', '。', '！', '？']
        has_multiple_sentences = sum(1 for c in response if c in sentence_endings) > 1
        
        if has_multiple_sentences:
            return 0.8
        
        return 0.6
    
    def _assess_accuracy(self, response: str, feedback: str) -> float:
        """基于显式反馈评估准确性"""
        if any(kw in feedback.lower() for kw in ["错误", "不对", "wrong", "incorrect"]):
            return 0.3
        if any(kw in feedback.lower() for kw in ["正确", "对了", "correct", "right"]):
            return 0.9
        return 0.7
    
    def _assess_accuracy_implicit(self, response: str) -> float:
        """隐式准确性评估"""
        # 检查是否包含置信度声明
        confidence_patterns = [
            r"(我认为|我觉得|可能|也许|probably|maybe|i think|i believe)",
            r"(根据|based on|according to)"
        ]
        
        for pattern in confidence_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return 0.7
        
        return 0.6
    
    def _assess_style_match(self, response: str, context: Dict[str, Any]) -> float:
        """评估风格匹配度"""
        # 可以基于人格参数与响应风格进行匹配
        # 这里实现简化版本
        return 0.7
    
    def _assess_tool_efficiency(self, context: Dict[str, Any]) -> float:
        """评估工具使用效率"""
        if not context or 'tools_used' not in context:
            return 0.5
        
        tools_used = context['tools_used']
        # 简单启发式：使用适当数量的工具是好的
        if len(tools_used) == 0:
            return 0.4
        elif len(tools_used) <= 2:
            return 0.8
        elif len(tools_used) <= 4:
            return 0.6
        else:
            return 0.4
    
    def _detect_implicit_signals(self, query: str, response: str) -> Dict[str, Any]:
        """检测隐式反馈信号"""
        signals = {}
        
        # 检测用户是否在追问
        follow_up_patterns = [
            r'(为什么|为什么|怎样|怎么|如何|为什么不)',
            r'(why|how|what about|but)'
        ]
        
        for pattern in follow_up_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                signals['follow_up_question'] = True
        
        # 检测响应长度
        signals['response_length'] = len(response)
        
        # 检测是否有代码块
        signals['has_code_block'] = '```' in response
        
        return signals
    
    def add_conversation_record(self, record: ConversationRecord):
        """添加对话记录到历史"""
        self.history.append(record)
        
        # 保留最近 1000 条记录
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
    
    def get_history_statistics(self) -> Dict[str, Any]:
        """获取历史统计"""
        if not self.history:
            return {"total": 0, "avg_score": 0}
        
        scores = [r.evaluation.overall_score 
                 for r in self.history 
                 if r.evaluation]
        
        return {
            "total": len(self.history),
            "with_evaluation": len(scores),
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "score_trend": self._calculate_trend(scores)
        }
    
    def _calculate_trend(self, scores: List[float]) -> str:
        """计算得分趋势"""
        if len(scores) < 10:
            return "insufficient_data"
        
        recent_avg = sum(scores[-5:]) / 5
        earlier_avg = sum(scores[-10:-5]) / 5
        
        if recent_avg > earlier_avg + 0.05:
            return "improving"
        elif recent_avg < earlier_avg - 0.05:
            return "declining"
        else:
            return "stable"
