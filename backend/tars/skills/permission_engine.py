"""技能权限引擎 — v2.5

工具 → 权限类别的映射表，以及运行时鉴权。
"""
from typing import List, Set

# 工具名 → 所需权限
TOOL_PERMISSION_MAP = {
    "shell": "shell",
    "python_exec": "shell",
    "file_write": "file_write",
    "file": "file_read",
    "file_list": "file_read",
    "web_search": "network",
    "web_fetch": "network",
    "weather": "network",
    "git_push": "git_push",
    "git_pull": "git_push",
    "cronjob": "system",
    "process": "system",
    "network": "network",
}

DANGEROUS_PERMISSIONS = {"shell", "file_write", "git_push", "system"}


class PermissionEngine:
    """检查技能是否有权限调用某工具"""

    def __init__(self, db=None):
        self.db = db

    def get_skill_permissions(self, skill_id: str) -> Set[str]:
        """获取技能被授予的权限集合"""
        if not self.db:
            return set()
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT granted_permissions FROM skills_v3 WHERE id = ?", (skill_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return set()
        import json
        try:
            return set(json.loads(row[0]))
        except json.JSONDecodeError:
            return set()

    def get_declared_permissions(self, skill_id: str) -> Set[str]:
        """获取技能声明的权限集合"""
        if not self.db:
            return set()
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT permissions FROM skills_v3 WHERE id = ?", (skill_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return set()
        import json
        try:
            return set(json.loads(row[0]))
        except json.JSONDecodeError:
            return set()

    def can_call(self, skill_id: str, tool_name: str) -> tuple:
        """检查技能是否可调用工具。返回 (allowed: bool, reason: str)"""
        if not skill_id:
            return True, ""  # 非技能触发的操作

        required = TOOL_PERMISSION_MAP.get(tool_name)
        if not required:
            return True, ""  # 无需权限的工具

        granted = self.get_skill_permissions(skill_id)
        if required in granted:
            return True, ""

        declared = self.get_declared_permissions(skill_id)
        if required in declared:
            return False, f"技能 '{skill_id}' 需要 '{required}' 权限但未被授权"

        return False, f"技能 '{skill_id}' 未声明 '{required}' 权限"

    def grant_permission(self, skill_id: str, permission: str) -> bool:
        """授予某权限"""
        if not self.db:
            return False
        granted = self.get_skill_permissions(skill_id)
        granted.add(permission)
        return self._save_granted(skill_id, granted)

    def revoke_permission(self, skill_id: str, permission: str) -> bool:
        """撤销某权限"""
        if not self.db:
            return False
        granted = self.get_skill_permissions(skill_id)
        granted.discard(permission)
        return self._save_granted(skill_id, granted)

    def _save_granted(self, skill_id: str, granted: set) -> bool:
        import json
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE skills_v3 SET granted_permissions = ? WHERE id = ?",
            (json.dumps(list(granted), ensure_ascii=False), skill_id),
        )
        conn.commit()
        return True

    def grant_all(self, skill_id: str) -> bool:
        """一键授予全部声明权限"""
        declared = self.get_declared_permissions(skill_id)
        return self._save_granted(skill_id, declared)


# 全局单例
permission_engine = PermissionEngine()
