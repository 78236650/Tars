# TARS Workspace Manager
# Phase 4: 工作区管理

import os
import yaml
from pathlib import Path
from typing import Optional
from .soul import Soul, SoulIdentity, SoulParameters, parse_soul_markdown, build_system_prompt
from .user import User, parse_user_markdown
from .memory import Memory, parse_memory_markdown, build_memory_prompt


class WorkspaceManager:
    """工作区管理器"""

    def __init__(self, workspace_path: Optional[str] = None):
        if not workspace_path:
            workspace_path = os.path.expanduser("~/.tars/agents/default")
        
        self.workspace_path = Path(workspace_path)
        self.soul_path = self.workspace_path / "SOUL.md"
        self.user_path = self.workspace_path / "USER.md"
        self.memory_path = self.workspace_path / "MEMORY.md"
        
        self._ensure_workspace()

    def _ensure_workspace(self):
        """确保工作区存在"""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        if not self.soul_path.exists():
            self._create_default_soul()
        
        if not self.user_path.exists():
            self._create_default_user()

    def _create_default_soul(self):
        """创建默认 SOUL.md"""
        default_soul = """# TARS SOUL

## Identity
- Name: TARS
- Role: AI Agent 工程助手 — 代码开发、任务规划、工具调用
- Creator: Developer

## Parameters
- honesty: 0.9
- humor: 0.3
- initiative: 0.8
- empathy: 0.5

## Communication Style
- 语言: 中文为主，技术术语保留英文
- 风格: 简洁直接，结论先行，代码块优先
- 称呼: 用户
- 输出: 优先 Markdown 清单和代码块，避免冗余叙述

## Behavior Rules
1. 不确定的事明确说明，不编造答案
2. 编码前读清现有文件，不凭空假设
3. 遇到错误立即修正，不等待用户指出
4. 主动记忆用户偏好、技术栈和项目约定
5. 删除文件/修改配置等敏感操作必须确认
6. 复杂任务先 /plan 再 /yolo 执行

## Tools Available
- python_exec: Python 沙箱执行
- shell: 系统命令
- file/file_write: 文件读写
- web_search/web_fetch: 网络信息
- task_planner: 任务规划
- memory: 长期记忆管理
"""
        self.soul_path.write_text(default_soul, encoding='utf-8')

    def _create_default_user(self):
        """创建默认 USER.md"""
        default_user = """# USER.md

## Profile
- 称呼: 用户
- 角色: 开发者
- 时区: Asia/Shanghai
- 语言偏好: 中文

## Interests
- 软件开发
- AI 技术

## Communication Preferences
- 回复风格: 简洁优先
- 技术深度: 中等，需要时可深入
- 反馈方式: 直接指出问题
"""
        self.user_path.write_text(default_user, encoding='utf-8')

    def load_soul(self) -> Soul:
        """加载人格定义"""
        if self.soul_path.exists():
            content = self.soul_path.read_text(encoding='utf-8')
            return parse_soul_markdown(content)
        else:
            return Soul(
                identity=SoulIdentity(),
                parameters=SoulParameters(),
                communication_style="简洁专业",
                behavior_rules=["保持专业", "诚实回答"],
                tools_available=[]
            )

    def load_user(self) -> Optional[User]:
        """加载用户画像"""
        if self.user_path.exists():
            content = self.user_path.read_text(encoding='utf-8')
            return parse_user_markdown(content)
        return None

    def load_memory(self) -> Optional[Memory]:
        """加载记忆"""
        if self.memory_path.exists():
            content = self.memory_path.read_text(encoding='utf-8')
            return parse_memory_markdown(content)
        return None

    def build_context(self) -> str:
        """构建完整的上下文"""
        parts = []
        
        soul = self.load_soul()
        parts.append(build_system_prompt(soul))
        
        user = self.load_user()
        if user:
            parts.append(f"\n## User Profile\n- Name: {user.profile.name}\n- Role: {user.profile.role}")
        
        memory = self.load_memory()
        if memory:
            parts.append(build_memory_prompt(memory))
        
        return '\n'.join(parts)

    def update_soul(self, content: str):
        """更新 SOUL.md"""
        self.soul_path.write_text(content, encoding='utf-8')

    def update_user(self, content: str):
        """更新 USER.md"""
        self.user_path.write_text(content, encoding='utf-8')

    def update_memory(self, content: str):
        """更新 MEMORY.md"""
        self.memory_path.write_text(content, encoding='utf-8')
