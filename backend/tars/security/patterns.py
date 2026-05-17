"""Sensitive information detection patterns — v4.0.0 Phase 1.

Regex-based detection for API keys, phone numbers, emails, bank cards,
private key blocks, and password-bearing JSON fields.
All patterns are compiled once at import time for performance.
"""

import re
from dataclasses import dataclass


@dataclass
class SensitiveMatch:
    """A single sensitive information match."""
    pattern_name: str
    start: int
    end: int
    matched_text: str


# ── Pattern definitions ────────────────────────────────────────────

SENSITIVE_PATTERNS = {
    # API keys: sk-proj-*, sk-ant-*, sk-*
    "api_key": re.compile(
        r'\b(sk-(?:proj|ant)-[a-zA-Z0-9]{20,})\b',
    ),
    # Bearer tokens: Authorization: Bearer <token> or Bearer <token>
    "bearer_token": re.compile(
        r'(?:Authorization:\s*)?Bearer\s+([A-Za-z0-9\-._~+/]+=*)',
        re.IGNORECASE,
    ),
    # Chinese mobile phone numbers (11 digits starting with 1, followed by 3-9)
    "phone_cn": re.compile(
        r'\b(1[3-9]\d{9})\b',
    ),
    # Email addresses
    "email": re.compile(
        r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b',
    ),
    # Bank card numbers (16-19 digits starting with 3-6, Luhn-plausible prefix)
    "bank_card": re.compile(
        r'\b([3-6]\d{15,18})\b',
    ),
    # Private key blocks: -----BEGIN ... PRIVATE KEY----- ... -----END ...
    "private_key": re.compile(
        r'(-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+|ENCRYPTED\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+|ENCRYPTED\s+)?PRIVATE\s+KEY-----)',
    ),
    # Password-bearing JSON: keys like "password", "secret", "token", "api_key"
    # Group 1 = key, Group 2 = value (including quotes)
    "password_field": re.compile(
        r'"[^"]*(?:password|secret|token|api_key|api_secret)[^"]*"\s*:\s*"([^"]{3,})"',
        re.IGNORECASE,
    ),
}


def match_sensitive(text: str) -> list[SensitiveMatch]:
    """Scan *text* and return all sensitive-information matches."""
    if not text:
        return []

    matches: list[SensitiveMatch] = []
    for name, pattern in SENSITIVE_PATTERNS.items():
        for m in pattern.finditer(text):
            # For multi-group patterns, use group(1) for the sensitive token
            if name == "password_field":
                matched = m.group(1)  # just the value
                matched_text = m.group(0)  # full key-value for context
            elif name == "bearer_token":
                matched = m.group(1)
                matched_text = matched
            else:
                matched = m.group(1) if m.lastindex else m.group(0)
                matched_text = matched
            matches.append(SensitiveMatch(
                pattern_name=name,
                start=m.start(),
                end=m.end(),
                matched_text=matched_text,
            ))
    return matches
