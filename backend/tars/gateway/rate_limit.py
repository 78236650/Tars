# TARS Gateway - Rate Limiter
# Layer 2: 速率限制

import time
from typing import Dict


class TokenBucket:
    """Token Bucket 算法实现"""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # 每秒补充的 token 数量
        self.capacity = capacity  # 桶的容量
        self.tokens = capacity
        self.last_update = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """尝试消费 tokens"""
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.rate
        )

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    """速率限制器"""

    def __init__(
        self,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500
    ):
        self.request_limit = TokenBucket(
            rate=requests_per_minute / 60.0,
            capacity=requests_per_minute
        )
        self.hourly_limit = TokenBucket(
            rate=requests_per_hour / 3600.0,
            capacity=requests_per_hour
        )
        self.limits: Dict[str, TokenBucket] = {}

    def check_rate_limit(self, user_id: str) -> tuple[bool, str]:
        """检查速率限制
        返回: (是否允许, 错误信息)
        """
        if not self.request_limit.consume():
            return False, "Rate limit exceeded: too many requests per minute"
        
        if not self.hourly_limit.consume():
            return False, "Rate limit exceeded: too many requests per hour"
        
        user_bucket = self.limits.get(user_id)
        if not user_bucket:
            user_bucket = TokenBucket(rate=1.0, capacity=10)
            self.limits[user_id] = user_bucket
        
        if not user_bucket.consume():
            return False, f"Rate limit exceeded for user {user_id}"
        
        return True, ""
