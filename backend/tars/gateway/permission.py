# TARS Gateway - Permission Management
# Layer 2: 权限管理模块

from enum import Enum
from typing import Optional, List


class UserRole(Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class PermissionManager:
    """权限管理器 - 负责权限验证和管理"""
    
    # 权限矩阵：{资源: {操作: [允许的角色]}}
    PERMISSIONS = {
        "session": {
            "create": [UserRole.ADMIN, UserRole.USER, UserRole.GUEST],
            "read_own": [UserRole.ADMIN, UserRole.USER],
            "read_others": [UserRole.ADMIN],
            "delete_own": [UserRole.ADMIN, UserRole.USER],
            "delete_others": [UserRole.ADMIN],
        },
        "skill": {
            "list": [UserRole.ADMIN, UserRole.USER, UserRole.GUEST],
            "activate": [UserRole.ADMIN],
            "deactivate": [UserRole.ADMIN],
            "create": [UserRole.ADMIN],
            "update": [UserRole.ADMIN],
            "delete": [UserRole.ADMIN],
        },
        "model": {
            "list": [UserRole.ADMIN, UserRole.USER, UserRole.GUEST],
            "switch": [UserRole.ADMIN, UserRole.USER],
        },
        "user": {
            "create": [UserRole.ADMIN],
            "list": [UserRole.ADMIN],
            "update": [UserRole.ADMIN],
            "delete": [UserRole.ADMIN],
            "read_own": [UserRole.ADMIN, UserRole.USER],
        },
        "memory": {
            "access": [UserRole.ADMIN, UserRole.USER],
            "read_own": [UserRole.ADMIN, UserRole.USER],
            "read_others": [UserRole.ADMIN],
        },
        "personality": {
            "read": [UserRole.ADMIN, UserRole.USER],
            "write": [UserRole.ADMIN, UserRole.USER],
        },
        "subagent": {
            "list": [UserRole.ADMIN, UserRole.USER, UserRole.GUEST],
            "configure": [UserRole.ADMIN, UserRole.USER],
            "invoke": [UserRole.ADMIN, UserRole.USER],
        },
    }
    
    def check_permission(self, user_role: UserRole, resource: str, action: str) -> bool:
        """
        检查用户是否有权限执行某个操作
        
        Args:
            user_role: 用户角色
            resource: 资源类型
            action: 操作类型
        
        Returns:
            bool: 是否有权限
        """
        if resource not in self.PERMISSIONS:
            return False
        if action not in self.PERMISSIONS[resource]:
            return False
        return user_role in self.PERMISSIONS[resource][action]
    
    def get_allowed_actions(self, user_role: UserRole, resource: str) -> List[str]:
        """
        获取用户对某个资源的所有允许操作
        
        Args:
            user_role: 用户角色
            resource: 资源类型
        
        Returns:
            List[str]: 允许的操作列表
        """
        if resource not in self.PERMISSIONS:
            return []
        
        allowed = []
        for action, roles in self.PERMISSIONS[resource].items():
            if user_role in roles:
                allowed.append(action)
        return allowed
    
    def is_admin(self, user_role: UserRole) -> bool:
        """检查是否是管理员"""
        return user_role == UserRole.ADMIN
    
    def is_authenticated(self, user_role: UserRole) -> bool:
        """检查是否是已认证用户（非访客）"""
        return user_role in [UserRole.ADMIN, UserRole.USER]
    
    def requires_authentication(self, resource: str, action: str) -> bool:
        """检查某个操作是否需要认证"""
        if resource not in self.PERMISSIONS:
            return True
        
        if action not in self.PERMISSIONS[resource]:
            return True
        
        roles = self.PERMISSIONS[resource][action]
        return UserRole.GUEST not in roles
