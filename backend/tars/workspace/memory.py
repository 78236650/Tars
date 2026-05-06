# TARS Memory - 长期记忆系统
# Phase 4: MEMORY 记忆管理

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone, timedelta


@dataclass
class MemoryCategory:
    name: str
    entries: list[str]


@dataclass
class Memory:
    categories: list[MemoryCategory]
    last_updated: datetime


def parse_memory_markdown(content: str) -> Memory:
    """解析 MEMORY.md 内容"""
    lines = content.strip().split('\n')
    
    categories = []
    current_category = None
    current_entries = []
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('§'):
            if current_category:
                categories.append(MemoryCategory(
                    name=current_category,
                    entries=current_entries
                ))
            current_category = ""
            current_entries = []
        elif line.startswith('## '):
            current_category = line[3:].strip()
        elif line and not line.startswith('#') and current_category:
            current_entries.append(line)
    
    if current_category:
        categories.append(MemoryCategory(
            name=current_category,
            entries=current_entries
        ))
    
    return Memory(
        categories=categories,
        last_updated=datetime.now(timezone(timedelta(hours=8)))
    )


def build_memory_prompt(memory: Memory) -> str:
    """从 Memory 构建记忆上下文"""
    if not memory.categories:
        return ""
    
    prompt_parts = ["## Relevant Memory"]
    
    for category in memory.categories:
        prompt_parts.append(f"\n### {category.name}")
        for entry in category.entries:
            prompt_parts.append(f"- {entry}")
    
    return '\n'.join(prompt_parts)
