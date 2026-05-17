"""Tests for TARS security sanitizer — Phase 1 Task 1-2.

Covers: pattern detection (Task 1) and sanitizer engine (Task 2).
TDD approach: tests written first, then implementation.
"""
import pytest
from tars.security.patterns import SENSITIVE_PATTERNS, match_sensitive, SensitiveMatch


# ── Task 1: Pattern Detection (9 tests) ────────────────────────────


class TestPatternDetection:
    """Verify each SENSITIVE_PATTERNS entry correctly detects targets."""

    def test_detect_api_key_sk(self):
        text = "my key is sk-proj-abc123def456ghi789jkl012"
        matches = match_sensitive(text)
        assert len(matches) == 1
        assert matches[0].pattern_name == "api_key"

    def test_detect_api_key_no_false_positive_short(self):
        """Short tokens like 'sk-' alone should not match."""
        text = "前缀 sk- 不是真实 key"
        matches = match_sensitive(text)
        assert len(matches) == 0

    def test_detect_api_key_bearer(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        matches = match_sensitive(text)
        assert len(matches) == 1
        assert matches[0].pattern_name == "bearer_token"

    def test_detect_phone_number(self):
        text = "联系我 13812345678 谢谢"
        matches = match_sensitive(text)
        assert len(matches) == 1
        assert matches[0].pattern_name == "phone_cn"

    def test_detect_email(self):
        text = "发送到 user@example.com"
        matches = match_sensitive(text)
        assert len(matches) == 1
        assert matches[0].pattern_name == "email"

    def test_detect_bank_card(self):
        text = "卡号 6222021234567890123"
        matches = match_sensitive(text)
        assert len(matches) == 1
        assert matches[0].pattern_name == "bank_card"

    def test_detect_private_key_block(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        matches = match_sensitive(text)
        assert len(matches) == 1
        assert matches[0].pattern_name == "private_key"

    def test_detect_password_in_json(self):
        text = '{"password": "mysecret123", "name": "test"}'
        matches = match_sensitive(text)
        assert len(matches) == 1
        assert matches[0].pattern_name == "password_field"

    def test_no_false_positive_normal_text(self):
        text = "今天天气不错，我们一起去世纪公园散步吧。项目进展顺利，版本号 3.9.1。"
        matches = match_sensitive(text)
        # Version numbers/正常对话不应触发误报
        assert len(matches) == 0

    def test_empty_text(self):
        matches = match_sensitive("")
        assert matches == []

    def test_multiple_patterns_in_one_text(self):
        text = "key: sk-proj-abc123def456ghi789jkl012, phone: 13812345678, email: test@example.com"
        matches = match_sensitive(text)
        assert len(matches) == 3
        names = {m.pattern_name for m in matches}
        assert names == {"api_key", "phone_cn", "email"}


# ── Task 2: Sanitizer Engine (7 tests) ─────────────────────────────


class TestSanitizer:
    """Verify the Sanitizer class correctly masks sensitive content."""

    def test_mask_api_key_partial(self, sanitizer_full):
        text = "sk-proj-abc123def456ghi789jkl012"
        result = sanitizer_full.sanitize(text)
        assert "sk-proj-abc123def456ghi789jkl012" not in result
        assert "sk-" in result

    def test_mask_phone_number_partial(self, sanitizer_full):
        text = "联系 13812345678"
        result = sanitizer_full.sanitize(text)
        assert "13812345678" not in result
        assert "138****" in result

    def test_mask_email_full(self, sanitizer_full):
        text = "发至 user@example.com"
        result = sanitizer_full.sanitize(text)
        assert "user@example.com" not in result
        assert "***@***" in result

    def test_redact_mode(self, sanitizer_redact):
        text = "key: sk-proj-abc123def456ghi789jkl012, phone: 13812345678"
        result = sanitizer_redact.sanitize(text)
        assert "sk-proj" not in result
        assert "13812345678" not in result
        assert "[REDACTED]" in result

    def test_whitelist_pattern(self, sanitizer_with_whitelist):
        text = "版本 3.9.1 和 3.9.2 的改进包括 1234567890123456 号工单"
        matches_before = match_sensitive(text)
        # Without whitelist this would have at least 1 match (16-digit number)
        result = sanitizer_with_whitelist.sanitize(text)
        # With whitelist for 16-digit numbers in known context, should pass through
        assert result == text

    def test_sanitize_empty_string(self, sanitizer_full):
        assert sanitizer_full.sanitize("") == ""

    def test_sanitize_no_sensitive_content(self, sanitizer_full):
        text = "今天是晴天，温度 25 度。"
        assert sanitizer_full.sanitize(text) == text


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sanitizer_full():
    from tars.security.sanitizer import Sanitizer
    return Sanitizer(mode="partial")


@pytest.fixture
def sanitizer_redact():
    from tars.security.sanitizer import Sanitizer
    return Sanitizer(mode="redact")


@pytest.fixture
def sanitizer_with_whitelist():
    from tars.security.sanitizer import Sanitizer
    return Sanitizer(
        mode="partial",
        whitelist_patterns=[r"工单\d*"],
    )
