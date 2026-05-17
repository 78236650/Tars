"""角色模板管理 — v4.0.2.

支持预置 + 自定义角色模板，控制工具权限、模块访问、并发限制。
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


@dataclass
class RoleTemplate:
    id: str
    name: str
    description: str = ""
    is_builtin: bool = False
    allowed_tools: list[str] | str = field(default_factory=list)  # "*" or list
    denied_tools: list[str] = field(default_factory=list)
    allowed_modules: list[str] = field(default_factory=list)
    resource_permissions: dict = field(default_factory=dict)
    workspace_restriction: bool = True
    max_concurrent: int = 1
    created_at: str = ""
    updated_at: str = ""


BUILTIN_TEMPLATES = [
    RoleTemplate(
        id="admin", name="系统管理员", description="全部权限，不可修改",
        is_builtin=True, allowed_tools="*", denied_tools=[],
        allowed_modules=["bi", "knowledge", "meeting", "skillhub"],
        workspace_restriction=False, max_concurrent=5,
    ),
    RoleTemplate(
        id="developer", name="开发者", description="信任用户，可执行代码",
        is_builtin=True,
        allowed_tools=["weather", "web_search", "web_fetch", "file", "file_list", "file_write", "shell", "command", "python_exec", "memory", "knowledge_search", "cronjob"],
        allowed_modules=["bi", "knowledge", "meeting", "skillhub"],
        workspace_restriction=True, max_concurrent=2,
    ),
    RoleTemplate(
        id="analyst", name="数据分析师", description="BI + Python + 知识库",
        is_builtin=True,
        allowed_tools=["weather", "web_search", "web_fetch", "python_exec", "file", "file_list", "file_write", "knowledge_search"],
        allowed_modules=["bi", "knowledge"],
        workspace_restriction=True, max_concurrent=2,
    ),
    RoleTemplate(
        id="operator", name="运维人员", description="Shell + 进程管理",
        is_builtin=True,
        allowed_tools=["shell", "command", "file", "file_list", "file_write", "process", "network"],
        allowed_modules=["bi", "knowledge", "meeting", "skillhub"],
        workspace_restriction=True, max_concurrent=2,
    ),
    RoleTemplate(
        id="standard", name="普通用户", description="基础工具，默认角色",
        is_builtin=True,
        allowed_tools=["weather", "web_search", "web_fetch", "file", "file_list", "memory", "knowledge_search"],
        allowed_modules=["knowledge", "skillhub"],
        workspace_restriction=True, max_concurrent=1,
    ),
    RoleTemplate(
        id="readonly", name="只读访客", description="最小权限",
        is_builtin=True,
        allowed_tools=["weather", "web_search"],
        allowed_modules=[],
        workspace_restriction=True, max_concurrent=1,
    ),
]


class RoleTemplateManager:
    def __init__(self, db):
        self._db = db
        self._ensure_table()
        self._seed_builtins()

    def _ensure_table(self):
        conn = self._db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                is_builtin INTEGER DEFAULT 0,
                allowed_tools TEXT DEFAULT '[]',
                denied_tools TEXT DEFAULT '[]',
                allowed_modules TEXT DEFAULT '[]',
                resource_permissions TEXT DEFAULT '{}',
                workspace_restriction INTEGER DEFAULT 1,
                max_concurrent INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()

    def _seed_builtins(self):
        conn = self._db._get_conn()
        cursor = conn.cursor()
        now = _now()
        for t in BUILTIN_TEMPLATES:
            cursor.execute(
                "INSERT OR IGNORE INTO role_templates (id, name, description, is_builtin, allowed_tools, denied_tools, allowed_modules, resource_permissions, workspace_restriction, max_concurrent, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)",
                (t.id, t.name, t.description,
                 json.dumps(t.allowed_tools, ensure_ascii=False),
                 json.dumps(t.denied_tools, ensure_ascii=False),
                 json.dumps(t.allowed_modules, ensure_ascii=False),
                 json.dumps(t.resource_permissions, ensure_ascii=False),
                 int(t.workspace_restriction), t.max_concurrent, now, now),
            )
        conn.commit()

    def _row_to_template(self, row) -> RoleTemplate:
        tools = json.loads(row[4]) if row[4] else []
        return RoleTemplate(
            id=row[0], name=row[1], description=row[2] or "",
            is_builtin=bool(row[3]),
            allowed_tools=tools,
            denied_tools=json.loads(row[5]) if row[5] else [],
            allowed_modules=json.loads(row[6]) if row[6] else [],
            resource_permissions=json.loads(row[7]) if row[7] else {},
            workspace_restriction=bool(row[8]),
            max_concurrent=row[9] or 1,
            created_at=row[10] or "", updated_at=row[11] or "",
        )

    def list_templates(self) -> list[RoleTemplate]:
        conn = self._db._get_conn()
        rows = conn.cursor().execute(
            "SELECT id, name, description, is_builtin, allowed_tools, denied_tools, allowed_modules, resource_permissions, workspace_restriction, max_concurrent, created_at, updated_at FROM role_templates ORDER BY is_builtin DESC, name"
        ).fetchall()
        return [self._row_to_template(r) for r in rows]

    def get_template(self, template_id: str) -> Optional[RoleTemplate]:
        conn = self._db._get_conn()
        row = conn.cursor().execute(
            "SELECT id, name, description, is_builtin, allowed_tools, denied_tools, allowed_modules, resource_permissions, workspace_restriction, max_concurrent, created_at, updated_at FROM role_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        return self._row_to_template(row) if row else None

    def create_template(self, id: str, name: str, description: str = "",
                        allowed_tools: list | str = None, denied_tools: list = None,
                        allowed_modules: list = None, max_concurrent: int = 1,
                        workspace_restriction: bool = True) -> RoleTemplate:
        now = _now()
        conn = self._db._get_conn()
        conn.cursor().execute(
            "INSERT INTO role_templates (id, name, description, is_builtin, allowed_tools, denied_tools, allowed_modules, resource_permissions, workspace_restriction, max_concurrent, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, ?, ?, ?, '{}', ?, ?, ?, ?)",
            (id, name, description,
             json.dumps(allowed_tools or [], ensure_ascii=False),
             json.dumps(denied_tools or [], ensure_ascii=False),
             json.dumps(allowed_modules or [], ensure_ascii=False),
             int(workspace_restriction), max_concurrent, now, now),
        )
        conn.commit()
        return self.get_template(id)

    def update_template(self, template_id: str, **kwargs) -> bool:
        t = self.get_template(template_id)
        if not t:
            return False
        if t.is_builtin:
            return False
        updates, params = [], []
        for key in ("name", "description", "max_concurrent", "workspace_restriction"):
            if key in kwargs:
                updates.append(f"{key} = ?")
                params.append(int(kwargs[key]) if key in ("max_concurrent", "workspace_restriction") else kwargs[key])
        for key in ("allowed_tools", "denied_tools", "allowed_modules"):
            if key in kwargs:
                updates.append(f"{key} = ?")
                params.append(json.dumps(kwargs[key], ensure_ascii=False))
        if not updates:
            return False
        updates.append("updated_at = ?")
        params.append(_now())
        params.append(template_id)
        conn = self._db._get_conn()
        conn.cursor().execute(f"UPDATE role_templates SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return True

    def delete_template(self, template_id: str) -> bool:
        t = self.get_template(template_id)
        if not t or t.is_builtin:
            return False
        conn = self._db._get_conn()
        conn.cursor().execute("DELETE FROM role_templates WHERE id = ? AND is_builtin = 0", (template_id,))
        conn.commit()
        return True

    def can_use_tool(self, template_id: str, tool_name: str) -> bool:
        t = self.get_template(template_id)
        if not t:
            return False
        if t.allowed_tools == "*":
            return True
        if tool_name in t.denied_tools:
            return False
        return tool_name in t.allowed_tools

    def can_access_module(self, template_id: str, module_name: str) -> bool:
        t = self.get_template(template_id)
        if not t:
            return False
        if t.allowed_tools == "*":
            return True
        return module_name in t.allowed_modules

    def get_user_permissions(self, template_id: str) -> dict:
        t = self.get_template(template_id) or self.get_template("standard")
        return {
            "role_template_id": t.id,
            "allowed_tools": t.allowed_tools,
            "denied_tools": t.denied_tools,
            "allowed_modules": t.allowed_modules,
            "max_concurrent": t.max_concurrent,
            "workspace_restriction": t.workspace_restriction,
        }


# 全局单例
role_template_manager: Optional[RoleTemplateManager] = None


def init_role_template_manager(db) -> RoleTemplateManager:
    global role_template_manager
    role_template_manager = RoleTemplateManager(db)
    return role_template_manager
