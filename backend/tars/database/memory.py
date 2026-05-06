# TARS Memory Manager
# Phase 5: 记忆管理器

import re
from typing import List, Optional
from .base import Database, Memory


class MemoryExtractor:
    """记忆提取器 - 从对话中提取记忆"""

    def __init__(self):
        self.patterns = {
            'user_preference': [
                r'我喜欢(.+?)。?',
                r'我偏好(.+?)。?',
                r'我通常(.+?)。?',
                r'不要(.+?)。?',
            ],
            'important_decision': [
                r'决定(.+?)。?',
                r'选择(.+?)作为(.+?)。?',
                r'采用(.+?)。?',
                r'我们(.+?)了(.+?)。?',
            ],
            'project_record': [
                r'完成了(.+?)。?',
                r'启动了(.+?)。?',
                r'使用了(.+?)技术。?',
                r'问题(.+?)已解决。?',
            ]
        }

    def extract(self, text: str) -> List[dict]:
        """从文本中提取记忆"""
        memories = []

        for category, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    content = match.group(0)
                    importance = self._calculate_importance(content, category)
                    memories.append({
                        'content': content,
                        'category': category,
                        'importance': importance
                    })

        return memories

    def _calculate_importance(self, content: str, category: str) -> float:
        """计算记忆重要性"""
        base_importance = 0.5

        if category == 'important_decision':
            base_importance = 0.8
        elif category == 'user_preference':
            base_importance = 0.7

        if len(content) > 50:
            base_importance += 0.1

        return min(base_importance, 1.0)


class MemoryManager:
    """记忆管理器"""

    def __init__(self, db: Database):
        self.db = db
        self.extractor = MemoryExtractor()

    def extract_and_save(self, conversation: str) -> List[Memory]:
        """提取对话中的记忆并保存"""
        extracted = self.extractor.extract(conversation)
        saved_memories = []

        for item in extracted:
            mem = self.db.add_memory(
                content=item['content'],
                category=item['category'],
                importance=item['importance']
            )
            saved_memories.append(mem)

        return saved_memories

    def search_related(self, query: str, limit: int = 5) -> List[Memory]:
        """搜索相关记忆"""
        return self.db.search_memories(query, limit)

    def get_context_for_query(self, query: str, limit: int = 3) -> str:
        """为查询获取相关记忆上下文"""
        memories = self.search_related(query, limit)

        if not memories:
            return ""

        context_parts = ["## Relevant Memory"]

        grouped = {}
        for mem in memories:
            if mem.category not in grouped:
                grouped[mem.category] = []
            grouped[mem.category].append(mem)

        for category, mems in grouped.items():
            context_parts.append(f"\n### {category.replace('_', ' ').title()}")
            for mem in mems:
                context_parts.append(f"- {mem.content}")

        return '\n'.join(context_parts)

    def add_manual_memory(self, content: str, category: str = "general", importance: float = 0.5) -> Memory:
        """手动添加记忆"""
        return self.db.add_memory(content, category, importance)

    def get_user_preferences(self) -> List[Memory]:
        """获取用户偏好"""
        return self.db.get_memories_by_category("user_preference")

    def get_important_decisions(self) -> List[Memory]:
        """获取重要决策"""
        return self.db.get_memories_by_category("important_decision")

    def get_project_records(self) -> List[Memory]:
        """获取项目记录"""
        return self.db.get_memories_by_category("project_record")
