import pytest
import os
from tars.gateway.auth import AuthManager, User
from tars.gateway.rate_limit import TokenBucket, RateLimiter
from tars.gateway.security import SecurityPolicy


class TestAuthManager:
    def test_verify_valid_api_key(self, monkeypatch):
        monkeypatch.setenv("TARS_API_KEY", "test_key_123")
        auth = AuthManager()
        user = auth.verify("Bearer test_key_123")
        
        assert user is not None
        assert user.id == "default_user"
        assert user.name == "Default User"

    def test_verify_api_key_without_bearer(self, monkeypatch):
        monkeypatch.setenv("TARS_API_KEY", "test_key_123")
        auth = AuthManager()
        user = auth.verify("test_key_123")
        
        assert user is not None
        assert user.api_key == "test_key_123"

    def test_verify_invalid_api_key(self, monkeypatch):
        monkeypatch.setenv("TARS_API_KEY", "valid_key")
        auth = AuthManager()
        user = auth.verify("invalid_key")
        
        assert user is None

    def test_verify_empty_api_key(self):
        auth = AuthManager()
        user = auth.verify(None)
        
        assert user is None

    def test_add_api_key(self):
        auth = AuthManager()
        user = User(id="user1", api_key="new_key", name="Test User", created_at="2024-01-01")
        auth.add_api_key(user)
        
        result = auth.verify("new_key")
        assert result is not None
        assert result.name == "Test User"


class TestTokenBucket:
    def test_consume_within_capacity(self):
        bucket = TokenBucket(rate=1.0, capacity=5)
        assert bucket.consume() is True
        assert bucket.tokens == 4

    def test_consume_exceeds_capacity(self):
        bucket = TokenBucket(rate=1.0, capacity=1)
        bucket.consume()  # tokens = 0
        assert bucket.consume() is False

    def test_tokens_refill_over_time(self):
        bucket = TokenBucket(rate=100.0, capacity=5)
        bucket.consume(5)  # tokens = 0
        import time
        time.sleep(0.01)  # 0.01秒应该补充1个token
        assert bucket.consume() is True

    def test_consume_multiple_tokens(self):
        bucket = TokenBucket(rate=1.0, capacity=10)
        assert bucket.consume(3) is True
        assert bucket.tokens == 7
        assert bucket.consume(8) is False  # 只有7个token


class TestRateLimiter:
    def test_check_rate_limit_allowed(self):
        limiter = RateLimiter(requests_per_minute=100, requests_per_hour=1000)
        allowed, message = limiter.check_rate_limit("user1")
        
        assert allowed is True
        assert message == ""

    def test_check_rate_limit_user_specific(self):
        limiter = RateLimiter(requests_per_minute=100, requests_per_hour=1000)
        
        for _ in range(10):
            allowed, _ = limiter.check_rate_limit("user1")
            assert allowed is True
        
        allowed, message = limiter.check_rate_limit("user1")
        assert allowed is False
        assert "Rate limit exceeded for user" in message


class TestSecurityPolicy:
    def test_check_command_safe(self):
        policy = SecurityPolicy()
        safe, message = policy.check_command("ls -la")
        
        assert safe is True
        assert message == ""

    def test_check_command_dangerous_rm_rf(self):
        policy = SecurityPolicy()
        safe, message = policy.check_command("rm -rf /")
        
        assert safe is False
        assert "dangerous pattern" in message

    def test_check_command_dangerous_sql(self):
        policy = SecurityPolicy()
        safe, message = policy.check_command("DROP TABLE users")
        
        assert safe is False
        assert "dangerous pattern" in message

    def test_check_path_allowed(self):
        policy = SecurityPolicy()
        safe, message = policy.check_path("/tmp/test.txt")
        
        assert safe is True
        assert message == ""

    def test_check_path_blocked(self):
        policy = SecurityPolicy()
        safe, message = policy.check_path("/etc/passwd")
        
        assert safe is False
        assert "protected" in message

    def test_check_content_safe(self):
        policy = SecurityPolicy()
        safe, message = policy.check_content("Hello world")
        
        assert safe is True
        assert message == ""

    def test_check_content_dangerous(self):
        policy = SecurityPolicy()
        safe, message = policy.check_content("eval('rm -rf /')")
        
        assert safe is False
        assert "dangerous pattern" in message

    def test_check_content_too_large(self):
        policy = SecurityPolicy()
        large_content = "x" * 100001
        safe, message = policy.check_content(large_content)
        
        assert safe is False
        assert "Content too large" in message
