"""
Prompt Tuner - 自动调优系统提示词和子代理提示词
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from .evaluator import EvaluationResult, ConversationRecord


@dataclass
class PromptVersion:
    """提示词版本记录"""
    version: int
    prompt_text: str
    created_at: datetime
    success_rate: float
    usage_count: int = 0
    feedbacks: List[EvaluationResult] = None


class PromptTuner:
    """提示词调优器"""
    
    def __init__(self):
        self.prompt_versions: Dict[str, List[PromptVersion]] = {}
        self.default_prompts = {
            'master': """You are TARS, a helpful AI assistant. Be friendly, professional, and helpful.""",
            'code': """You are a coding assistant. Help write, debug, and optimize code.""",
            'writing': """You are a writing assistant. Help create and edit content.""",
            'data': """You are a data analysis assistant. Help analyze and visualize data.""",
            'research': """You are a research assistant. Help find and summarize information.""",
            'plan': """You are a planning assistant. Help organize tasks and create plans."""
        }
        
        # 初始化默认版本
        for prompt_type, prompt in self.default_prompts.items():
            self.prompt_versions[prompt_type] = [
                PromptVersion(
                    version=1,
                    prompt_text=prompt,
                    created_at=datetime.now(),
                    success_rate=0.7,
                    feedbacks=[]
                )
            ]
    
    def tune_system_prompt(self, history_records: List[ConversationRecord], 
                          prompt_type: str = 'master') -> str:
        """调优系统提示词"""
        
        current_prompt = self.get_current_prompt(prompt_type)
        
        if len(history_records) < 20:
            return current_prompt
        
        feedbacks = [r.evaluation for r in history_records 
                   if r.evaluation and r.context.get('prompt_type') == prompt_type]
        
        if len(feedbacks) < 10:
            return current_prompt
        
        avg_score = sum(f.overall_score for f in feedbacks) / len(feedbacks)
        
        if avg_score > 0.8:
            return current_prompt
        
        suggestions = self._generate_improvement_suggestions(feedbacks)
        improved_prompt = self._apply_suggestions(current_prompt, suggestions)
        
        version = len(self.prompt_versions.get(prompt_type, [])) + 1
        new_version = PromptVersion(
            version=version,
            prompt_text=improved_prompt,
            created_at=datetime.now(),
            success_rate=0.7,
            feedbacks=[]
        )
        
        if prompt_type not in self.prompt_versions:
            self.prompt_versions[prompt_type] = []
        self.prompt_versions[prompt_type].append(new_version)
        
        return improved_prompt
    
    def get_current_prompt(
        self,
        prompt_type: str,
        tenant_id: str = "default",
        apply_engine=None,
    ) -> str:
        """Get current prompt — prefer workspace file, fallback to in-memory."""
        if apply_engine is not None:
            file_prompt = apply_engine.read_prompt(tenant_id, prompt_type)
            if file_prompt.strip():
                return file_prompt
        if prompt_type not in self.prompt_versions:
            return self.default_prompts.get(prompt_type, "")
        
        versions = self.prompt_versions[prompt_type]
        if not versions:
            return self.default_prompts.get(prompt_type, "")
        
        return versions[-1].prompt_text
    
    def _generate_improvement_suggestions(self, 
                                         feedbacks: List[EvaluationResult]) -> Dict[str, float]:
        """根据反馈生成改进建议"""
        suggestions = {}
        
        relevance_scores = [f.relevance for f in feedbacks]
        completeness_scores = [f.completeness for f in feedbacks]
        style_scores = [f.style_match for f in feedbacks]
        
        avg_relevance = sum(relevance_scores) / len(relevance_scores)
        avg_completeness = sum(completeness_scores) / len(completeness_scores)
        avg_style = sum(style_scores) / len(style_scores)
        
        if avg_relevance < 0.6:
            suggestions['improve_relevance'] = 0.7 - avg_relevance
        if avg_completeness < 0.6:
            suggestions['improve_completeness'] = 0.7 - avg_completeness
        if avg_style < 0.6:
            suggestions['improve_style'] = 0.7 - avg_style
        
        return suggestions
    
    def _apply_suggestions(self, prompt: str, suggestions: Dict[str, float]) -> str:
        """Apply improvement suggestions to prompt (deduplicated)."""
        improved_prompt = prompt
        snippets = {
            "improve_relevance": "\n\nImportant: Focus on being highly relevant to the user's question.",
            "improve_completeness": "\n\nImportant: Provide complete and comprehensive answers.",
            "improve_style": "\n\nImportant: Maintain consistent and appropriate tone and style.",
        }
        for key, snippet in snippets.items():
            if key in suggestions and snippet.strip() not in improved_prompt:
                improved_prompt += snippet
        return improved_prompt
    
    def record_feedback(self, prompt_type: str, evaluation: EvaluationResult):
        """记录提示词使用反馈"""
        
        if prompt_type not in self.prompt_versions:
            return
        
        versions = self.prompt_versions[prompt_type]
        if not versions:
            return
        
        current = versions[-1]
        current.feedbacks.append(evaluation)
        current.usage_count += 1
        
        total_feedbacks = len(current.feedbacks)
        if total_feedbacks > 0:
            current.success_rate = sum(f.overall_score for f in current.feedbacks) / total_feedbacks
    
    def get_prompt_history(self, prompt_type: str) -> List[Dict[str, Any]]:
        """获取提示词版本历史"""
        
        if prompt_type not in self.prompt_versions:
            return []
        
        return [
            {
                'version': v.version,
                'prompt_text': v.prompt_text,
                'created_at': v.created_at.isoformat(),
                'success_rate': v.success_rate,
                'usage_count': v.usage_count
            }
            for v in self.prompt_versions[prompt_type]
        ]
    
    def rollback_prompt(
        self,
        prompt_type: str,
        version: int,
        *,
        tenant_id: str = "default",
        apply_engine=None,
    ) -> bool:
        """回滚到指定版本；若提供 apply_engine 则同步写回 workspace 文件。"""
        
        if prompt_type not in self.prompt_versions:
            return False
        
        versions = self.prompt_versions[prompt_type]
        target_version = next((v for v in versions if v.version == version), None)
        
        if not target_version:
            return False
        
        new_version = PromptVersion(
            version=len(versions) + 1,
            prompt_text=target_version.prompt_text,
            created_at=datetime.now(),
            success_rate=target_version.success_rate,
            usage_count=0,
            feedbacks=[]
        )
        versions.append(new_version)

        if apply_engine is not None:
            apply_engine.apply_prompt(tenant_id, prompt_type, target_version.prompt_text)
        
        return True
