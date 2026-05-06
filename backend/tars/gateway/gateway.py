# TARS Gateway - Main Gateway
# Layer 2: 网关主类

from typing import Optional, Tuple
from .auth import AuthManager, User
from .rate_limit import RateLimiter
from .security import SecurityPolicy


class Gateway:
    """Gateway 主类 - 整合所有网关功能"""

    def __init__(
        self,
        require_auth: bool = False,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500
    ):
        self.auth = AuthManager()
        self.rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour
        )
        self.security = SecurityPolicy()
        self.require_auth = require_auth

    def verify_request(
        self,
        api_key: Optional[str] = None
    ) -> Tuple[bool, Optional[User], str]:
        """验证请求
        返回: (是否通过, 用户对象, 错误信息)
        """
        if self.require_auth:
            user = self.auth.verify(api_key)
            if not user:
                return False, None, "Authentication required"
            return True, user, ""
        return True, None, ""

    def check_rate_limit(self, user_id: str = "anonymous") -> Tuple[bool, str]:
        """检查速率限制
        返回: (是否允许, 错误信息)
        """
        return self.rate_limiter.check_rate_limit(user_id)

    def check_command(self, command: str) -> Tuple[bool, str]:
        """检查命令安全性
        返回: (是否安全, 错误信息)
        """
        return self.security.check_command(command)

    def check_path(self, path: str) -> Tuple[bool, str]:
        """检查路径安全性
        返回: (是否可访问, 错误信息)
        """
        return self.security.check_path(path)

    def check_content(self, content: str) -> Tuple[bool, str]:
        """检查内容安全性
        返回: (是否安全, 错误信息)
        """
        return self.security.check_content(content)
