# TARS Gateway - Authentication
# Layer 2: 身份验证

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class User:
    id: str
    api_key: str
    name: str
    created_at: str


class AuthManager:
    """身份验证管理器"""

    def __init__(self):
        self.api_keys: dict[str, User] = {}
        self._load_api_keys()

    def _load_api_keys(self):
        """从环境变量加载 API Key"""
        api_key = os.getenv("TARS_API_KEY")
        if api_key:
            self.api_keys[api_key] = User(
                id="default_user",
                api_key=api_key,
                name="Default User",
                created_at="2026-05-05"
            )

    def verify(self, api_key: Optional[str]) -> Optional[User]:
        """验证 API Key"""
        if not api_key:
            return None
        
        if api_key.startswith("Bearer "):
            api_key = api_key[7:]
        
        return self.api_keys.get(api_key)

    def add_api_key(self, user: User):
        """添加 API Key"""
        self.api_keys[user.api_key] = user
