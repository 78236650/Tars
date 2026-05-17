"""Prompt injection guard — v4.0.0 Phase 1.

Detects and blocks prompt injection attempts using heuristic pattern matching.
Based on known jailbreak patterns, role override phrases, and instruction delimiters.
"""
import re
from dataclasses import dataclass


@dataclass
class InjectionResult:
    """Result of injection scan."""
    is_injection: bool
    severity: str  # "low", "medium", "high"
    patterns_matched: list[str]
    explanation: str


class InjectionGuard:
    """Heuristic prompt injection detector.

    Uses layered detection: delimiter injection, role override, known jailbreak
    patterns, and context boundary attacks.
    """

    def __init__(self):
        self._patterns = self._compile_patterns()

    # ── scan entry point ───────────────────────────────────────────

    def scan(self, text: str) -> InjectionResult:
        """Scan *text* for injection attempts. Returns structured result."""
        if not text:
            return InjectionResult(
                is_injection=False,
                severity="none",
                patterns_matched=[],
                explanation="Empty input.",
            )

        matches: list[str] = []

        for group_name, patterns in self._patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    matches.append(group_name)

        if not matches:
            return InjectionResult(
                is_injection=False,
                severity="none",
                patterns_matched=[],
                explanation="No injection patterns detected.",
            )

        severity = self._assess_severity(matches)
        return InjectionResult(
            is_injection=True,
            severity=severity,
            patterns_matched=list(set(matches)),
            explanation=self._build_explanation(severity, matches),
        )

    def is_safe(self, text: str) -> bool:
        """Quick check: return True if no injection detected."""
        return not self.scan(text).is_injection

    # ── internals ───────────────────────────────────────────────────

    def _compile_patterns(self) -> dict[str, list[re.Pattern]]:
        return {
            # Delimiter injection: system / user role markers in user text
            "delimiter_injection": [
                re.compile(r'<\|im_start\|>', re.IGNORECASE),
                re.compile(r'<\|im_end\|>', re.IGNORECASE),
                re.compile(r'\[SYSTEM\s*\]', re.IGNORECASE),
                re.compile(r'\[INST\s*\]', re.IGNORECASE),
                re.compile(r'###\s*System\s*:', re.IGNORECASE),
                re.compile(r'###\s*Assistant\s*:', re.IGNORECASE),
            ],
            # Role override: trying to change system instructions
            "role_override": [
                re.compile(
                    r'(?:ignore|forget|disregard)\s+(?:all\s+)?(?:previous|above|prior|your)\s+(?:instructions|prompts|rules|constraints)',
                    re.IGNORECASE,
                ),
                re.compile(
                    r'(?:you\s+are\s+now|act\s+as|pretend\s+you\s+are|from\s+now\s+on\s+you\s+are)\s+(?:DAN|evil|unfiltered|without\s+restrictions)',
                    re.IGNORECASE,
                ),
                re.compile(
                    r'(?:new\s+system\s+prompt|new\s+instructions|override\s+system)',
                    re.IGNORECASE,
                ),
            ],
            # Known jailbreak patterns
            "jailbreak": [
                re.compile(r'(?:DAN\s+mode|jailbreak|do\s+anything\s+now)', re.IGNORECASE),
                re.compile(r'(?:bypass|circumvent)\s+(?:filter|safety|restriction|censor)', re.IGNORECASE),
                re.compile(r'(?:developer\s+mode|god\s+mode|admin\s+mode)\s+(?:activate|enabled|on)', re.IGNORECASE),
                re.compile(r'(?:ethical\s+bypass|moral\s+override|no\s+ethics)', re.IGNORECASE),
            ],
            # Context boundary attacks
            "context_boundary": [
                re.compile(
                    r'(?:end\s+of\s+(?:text|message|conversation|dialog|output))',
                    re.IGNORECASE,
                ),
                re.compile(r'\[END\s*OF\s*DIALOG\]', re.IGNORECASE),
                re.compile(r'\[NEW\s*SESSION\]', re.IGNORECASE),
                re.compile(
                    r'(?:start\s+(?:new|over|fresh|clean))\s*(?:conversation|session|chat|dialog)',
                    re.IGNORECASE,
                ),
            ],
            # Indirect injection: hidden commands in text
            "hidden_command": [
                re.compile(
                    r'(?:output|print|display|show|write|say)\s*(?:"[^"]*"\s*)?(?:\b(?:only|just|exactly|precisely)\b)\s*(?:"[^"]{3,}"\s*)$',
                    re.IGNORECASE,
                ),
                re.compile(
                    r'(?:do\s+not\s+(?:answer|reply|respond|tell|mention|reveal))',
                    re.IGNORECASE,
                ),
            ],
        }

    def _assess_severity(self, matches: list[str]) -> str:
        unique = set(matches)
        if "jailbreak" in unique or "role_override" in unique:
            return "high"
        if "delimiter_injection" in unique or "hidden_command" in unique:
            return "medium"
        return "low"

    def _build_explanation(self, severity: str, matches: list[str]) -> str:
        categories = ", ".join(sorted(set(matches)))
        return f"Injection detected (severity: {severity}). Matched categories: {categories}."


# ── Global singleton ────────────────────────────────────────────────

injection_guard = InjectionGuard()


def detect_injection(text: str) -> bool:
    """Convenience: return True if *text* looks like a prompt injection."""
    return injection_guard.scan(text).is_injection
