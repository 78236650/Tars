"""
Evolution Manager - 整合所有自进化模块的核心管理器
"""
import asyncio
import os
import json
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime

from .evaluator import (
    ResponseEvaluator, 
    EvaluationResult, 
    ConversationRecord,
    FeedbackType
)
from .optimizer import PersonalityOptimizer, SubAgentOptimizer
from .prompt_tuner import PromptTuner
from .case_capture import CaseCapture
from .case_distiller import CaseDistiller


class EvolutionManager:
    """自进化管理器 - 整合所有自进化功能"""
    
    def __init__(self, data_dir: Optional[Path] = None, db=None):
        self.data_dir = data_dir or Path.home() / '.tars' / 'evolution'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = db
        
        self.evaluator = ResponseEvaluator()
        self.personality_optimizer = PersonalityOptimizer()
        self.subagent_optimizer = SubAgentOptimizer()
        self.prompt_tuner = PromptTuner()

        self._feedback_collector = None
        self._apply_engine = None
        self._orchestrator = None
        self._case_capture = None
        self._case_distiller = None
        if db is not None:
            from .feedback_collector import FeedbackCollector
            from .apply_engine import ApplyEngine
            from .orchestrator import EvolutionOrchestrator

            self._feedback_collector = FeedbackCollector(db)
            self._apply_engine = ApplyEngine(db)
            self._case_capture = CaseCapture(db)
            self._case_distiller = CaseDistiller(db, self._case_capture)

            # v5.0.5/A3: Memory ↔ Evolution 桥梁
            from .memory_analyzer import MemoryAwareAnalyzer
            from .memory_feedback_bridge import MemoryFeedbackBridge

            self._memory_analyzer = MemoryAwareAnalyzer(db)
            self._memory_bridge = MemoryFeedbackBridge(db)

            self._orchestrator = EvolutionOrchestrator(
                db,
                feedback_collector=self._feedback_collector,
                apply_engine=self._apply_engine,
                personality_optimizer=self.personality_optimizer,
                subagent_optimizer=self.subagent_optimizer,
                prompt_tuner=self.prompt_tuner,
                evaluator=self.evaluator,
                case_distiller=self._case_distiller,
                memory_analyzer=self._memory_analyzer,
                memory_bridge=self._memory_bridge,
            )
        else:
            self._case_capture = CaseCapture(db) if db else None
        
        self._enabled = True
        self._auto_optimize = True
        self._optimize_interval = 50  # 每50次对话优化一次
        self._conversation_count = 0
        self._optimize_lock: Optional[asyncio.Lock] = None
        self._last_state_save_at: Optional[float] = None
        
        self._load_state()
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        self._save_state()
    
    @property
    def auto_optimize(self) -> bool:
        return self._auto_optimize
    
    @auto_optimize.setter
    def auto_optimize(self, value: bool):
        self._auto_optimize = value
        self._save_state()
    
    def record_conversation(self, conversation_id: str, query: str, response: str,
                          context: Dict[str, Any] = None,
                          explicit_feedback: Optional[str] = None) -> EvaluationResult:
        """记录对话并进行评估"""
        
        context = context or {}
        
        evaluation = self.evaluator.evaluate(
            query=query,
            response=response,
            context=context,
            explicit_feedback=explicit_feedback
        )
        
        record = ConversationRecord(
            conversation_id=conversation_id,
            query=query,
            response=response,
            timestamp=datetime.now(),
            evaluation=evaluation,
            context=context,
            tools_used=context.get('tools_used', []),
            subagent_used=context.get('subagent_used')
        )
        
        self.evaluator.add_conversation_record(record)
        self._conversation_count += 1
        
        if 'prompt_type' in context:
            self.prompt_tuner.record_feedback(
                context['prompt_type'],
                evaluation
            )
        
        if self._auto_optimize and self._enabled and self._conversation_count % self._optimize_interval == 0:
            self._schedule_optimize(context.get("tenant_id", "default"))
        
        from .config import get_evolution_config
        cfg = get_evolution_config()
        if self._conversation_count % max(cfg.ingest.save_state_every_n_turns, 1) == 0:
            self._maybe_save_state()
        
        return evaluation
    
    def _maybe_save_state(self) -> None:
        import time
        from .config import get_evolution_config

        cfg = get_evolution_config()
        now = time.monotonic()
        min_interval = max(getattr(cfg.ingest, "save_state_min_interval_seconds", 0), 0)
        if (
            self._last_state_save_at is not None
            and min_interval > 0
            and (now - self._last_state_save_at) < min_interval
        ):
            return
        self._save_state()
        self._last_state_save_at = now
    
    def _schedule_optimize(self, tenant_id: str) -> None:
        from .config import get_evolution_config

        if not get_evolution_config().ingest.optimize_async:
            self.optimize(tenant_id=tenant_id)
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.optimize(tenant_id=tenant_id)
            return
        loop.create_task(self._async_optimize(tenant_id))

    async def _async_optimize(self, tenant_id: str) -> None:
        if self._optimize_lock is None:
            self._optimize_lock = asyncio.Lock()
        async with self._optimize_lock:
            self.optimize(tenant_id=tenant_id)

    def ingest_turn(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str,
        query: str,
        response: str,
        *,
        tools_used: Optional[list] = None,
        tool_results: Optional[list] = None,
        subagent: Optional[str] = None,
        skill_id: Optional[str] = None,
    ) -> Optional[EvaluationResult]:
        """Agent 回合结束 — 评估 + 计数 + 可选触发 optimize（工具反馈由 Dispatcher 写入）。"""
        if not self._enabled:
            return None
        tools_used = tools_used or []
        if tool_results:
            tools_used = [str(t.get("name", "")) for t in tool_results if t.get("name")]
        evaluation = self.record_conversation(
            session_id,
            query,
            response,
            context={
                "tools_used": tools_used,
                "subagent_used": subagent,
                "skill_id": skill_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        )

        # Self-Evolving Skills: capture agent trajectory as a Case
        if self._case_capture:
            try:
                self._case_capture.record_turn(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                    query=query,
                    tools_used=tools_used,
                    tool_results=tool_results,
                    skill_id=skill_id,
                    subagent=subagent,
                    success=True,
                )
            except Exception as exc:
                print(f"[Evolution] case_capture.record_turn failed: {exc}")

        return evaluation

    @property
    def feedback_collector(self):
        return self._feedback_collector

    def optimize(self, tenant_id: str = "default") -> Dict[str, Any]:
        """触发一次完整的优化流程"""
        if self._orchestrator:
            return self._orchestrator.optimize(tenant_id=tenant_id)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'personality_optimized': False,
            'subagent_optimized': False,
            'prompts_tuned': False
        }
        
        history = self.evaluator.history
        
        if len(history) >= 20:
            current_personality = self._get_current_personality()
            if current_personality:
                optimized_params = self.personality_optimizer.optimize(
                    current_personality,
                    history
                )
                self._apply_personality_update(optimized_params)
                results['personality_optimized'] = True
                results['new_personality'] = optimized_params
            
            sa_weights = self.subagent_optimizer.optimize_task_delegation(history)
            results['subagent_optimized'] = True
            results['subagent_weights'] = sa_weights
            
            sa_personality = self.subagent_optimizer.optimize_personality_weights(history)
            results['subagent_personality'] = sa_personality
            
            for prompt_type in ['master', 'code', 'writing', 'data', 'research', 'plan']:
                self.prompt_tuner.tune_system_prompt(history, prompt_type)
            results['prompts_tuned'] = True
        
        self._save_state()
        
        return results
    
    def get_personality_suggestions(self) -> Dict[str, float]:
        """获取人格参数优化建议"""
        
        if len(self.evaluator.history) < 10:
            return {}
        
        current_params = self._get_current_personality() or {}
        suggested_params = self.personality_optimizer.optimize(
            current_params,
            self.evaluator.history
        )
        
        suggestions = {}
        for name, current in current_params.items():
            suggested = suggested_params.get(name, current)
            if abs(suggested - current) > 0.05:
                suggestions[name] = suggested
        
        return suggestions
    
    def get_stats(self) -> Dict[str, Any]:
        """获取自进化系统的统计信息"""
        
        stats = self.evaluator.get_history_statistics()
        
        stats.update({
            'enabled': self._enabled,
            'auto_optimize': self._auto_optimize,
            'conversation_count': self._conversation_count,
            'subagent_recommendations': self.subagent_optimizer.get_recommendations(),
            'prompt_history': {
                pt: self.prompt_tuner.get_prompt_history(pt)
                for pt in ['master', 'code', 'writing', 'data', 'research', 'plan']
            }
        })
        
        return stats
    
    def _get_current_personality(self) -> Optional[Dict[str, float]]:
        """获取当前人格参数（从 tenant workspace 或默认）"""
        if self._apply_engine:
            try:
                return self._apply_engine.read_personality_params("default")
            except Exception:
                pass
        default_params = {
            'honesty': 0.9,
            'humor': 0.7,
            'initiative': 0.8,
            'empathy': 0.7,
            'formality': 0.5,
            'creativity': 0.6,
            'conciseness': 0.5,
            'technical_depth': 0.6,
            'curiosity': 0.7,
            'skepticism': 0.3
        }
        return default_params
    
    def _apply_personality_update(self, new_params: Dict[str, float]):
        """应用人格参数更新"""
        if self._apply_engine:
            self._apply_engine.apply_personality("default", new_params)
    
    def _save_state(self):
        """保存状态到文件"""
        state_file = self.data_dir / 'state.json'
        
        state = {
            'enabled': self._enabled,
            'auto_optimize': self._auto_optimize,
            'optimize_interval': self._optimize_interval,
            'conversation_count': self._conversation_count
        }
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def _load_state(self):
        """从文件加载状态"""
        state_file = self.data_dir / 'state.json'
        
        if not state_file.exists():
            return
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            self._enabled = state.get('enabled', True)
            self._auto_optimize = state.get('auto_optimize', True)
            self._optimize_interval = state.get('optimize_interval', 50)
            self._conversation_count = state.get('conversation_count', 0)
        except Exception:
            pass
