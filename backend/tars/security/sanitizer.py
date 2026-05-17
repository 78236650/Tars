"""Sanitizer engine core — v4.0.0 Phase 1.

Scans text for sensitive information and masks it according to configurable
mode (partial mask or full redaction), with optional whitelist rules.
"""

import re
from typing import Optional

from .patterns import match_sensitive


class Sanitizer:
    """Sensitive information masking engine.
    
    Modes:
      - "partial": keep prefix + last 4 chars for structured data, 
         full mask for unstructured (email, private key).
      - "redact": replace every match with "[REDACTED]".
    
    Whitelist: patterns that, when found in surrounding context, 
    prevent a match from being masked.
    """

    def __init__(
        self,
        mode: str = "partial",
        whitelist_patterns: Optional[list[str]] = None,
    ):
        self.mode = mode
        self._whitelist_patterns: list[re.Pattern] = []
        if whitelist_patterns:
            self._whitelist_patterns = [
                re.compile(p) for p in whitelist_patterns
            ]

    def sanitize(self, text: str) -> str:
        """Return *text* with all sensitive content masked."""
        if not text:
            return ""

        matches = match_sensitive(text)
        if not matches:
            return text

        # Build replacement list sorted by start position (process right-to-left
        # so indices stay valid).
        replacements = []
        for m in matches:
            if self._is_whitelisted(m, text):
                continue
            masked = self._mask(m)
            replacements.append((m.start, m.end, masked))

        # Apply replacements from right to left
        replacements.sort(key=lambda r: r[0], reverse=True)
        result = text
        for start, end, masked in replacements:
            result = result[:start] + masked + result[end:]

        return result

    # ── internals ───────────────────────────────────────────────────

    def _is_whitelisted(self, match, text: str) -> bool:
        """Return True when a whitelist pattern is found near the match."""
        for pat in self._whitelist_patterns:
            # Check 20 chars before the match
            ctx_start = max(0, match.start - 20)
            ctx_end = min(len(text), match.end + 20)
            if pat.search(text, ctx_start, ctx_end):
                return True
        return False

    def _mask(self, match) -> str:
        if self.mode == "redact":
            return "[REDACTED]"

        name = match.pattern_name
        text = match.matched_text

        if name == "api_key":
            # sk-proj-abc…def → sk-proj-****def
            dash = text.rfind("-")
            if dash > 0:
                prefix = text[:dash + 1]
                suffix = text[-4:]
                return f"{prefix}****{suffix}"
            return text[:3] + "****" + text[-4:]

        if name == "bearer_token":
            # eyJh… → eyJ****…
            visible = min(3, len(text) - 4)
            return text[:visible] + "****" + text[-4:]

        if name == "phone_cn":
            # 13812345678 → 138****5678
            return text[:3] + "****" + text[-4:]

        if name == "email":
            return "***@***"

        if name == "bank_card":
            # 6222…0123 → 6222****0123
            return text[:4] + "****" + text[-4:]

        if name == "private_key":
            return "[PRIVATE KEY REDACTED]"

        if name == "password_field":
            return re.sub(
                r'("(?:password|secret|token|api_key|api_secret)[^"]*")\s*:\s*"[^"]+"',
                r'\1: "****"',
                match.matched_text,
                flags=re.IGNORECASE,
            )

        return "[REDACTED]"


# ── Global singleton ────────────────────────────────────────────────

sanitizer = Sanitizer(mode="partial")
