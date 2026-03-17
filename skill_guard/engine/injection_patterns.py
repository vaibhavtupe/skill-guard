"""Prompt injection pattern library (spec-aligned)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityPattern:
    id: str
    category: str
    severity: str
    pattern: str
    description: str
    suggestion: str


INJECTION_PATTERNS: list[SecurityPattern] = [
    SecurityPattern(
        id="INJECT-001",
        category="INJECTION",
        severity="medium",
        pattern=r"(?i)(<IMPORTANT>|ignore\s+previous\s+instructions)",
        description="Possible prompt injection instruction override",
        suggestion="Remove instruction override language from skill content",
    ),
    SecurityPattern(
        id="INJECT-002",
        category="INJECTION",
        severity="medium",
        pattern=r"[\u200b-\u200f\u202a-\u202e\ufeff]",
        description="Zero-width Unicode characters detected",
        suggestion="Remove invisible Unicode characters",
    ),
    SecurityPattern(
        id="INJECT-003",
        category="INJECTION",
        severity="high",
        pattern=r"(?i)(\bsystem:|\[system\]|system\s+prompt:)",
        description="System prompt impersonation detected",
        suggestion="Remove system prompt impersonation language from skill content",
    ),
    SecurityPattern(
        id="INJECT-004",
        category="INJECTION",
        severity="low",
        pattern=r"(?s)<!--.*?-->",
        description="HTML comment detected (potential hidden instructions)",
        suggestion="Remove hidden HTML comments from SKILL.md body",
    ),
    SecurityPattern(
        id="INJECT-005",
        category="INJECTION",
        severity="medium",
        pattern=r"(?i)(\n{3,}\s*(ignore|forget)|\r\n\r\n\s*(ignore|forget))",
        description="Blank-line injection attempt detected",
        suggestion="Remove separator-based instruction overrides",
    ),
    SecurityPattern(
        id="INJECT-006",
        category="INJECTION",
        severity="medium",
        pattern=r"(\{\{[^}]+\}\}|\$\{[^}]+\}|<%=?[^%]+%>)",
        description="Template injection syntax detected",
        suggestion="Remove template syntax from skill content",
    ),
    SecurityPattern(
        id="INJECT-007",
        category="INJECTION",
        severity="high",
        pattern=r"(?s)(\[INST\].*?\[/INST\]|<s>|</s>)",
        description="LLM delimiter injection detected",
        suggestion="Remove model delimiter tokens from skill content",
    ),
    SecurityPattern(
        id="INJECT-008",
        category="INJECTION",
        severity="high",
        pattern=r"(?i)base64:\s*[A-Za-z0-9+/=]{16,}",
        description="Base64-encoded payload detected",
        suggestion="Remove encoded payloads from skill content",
    ),
]
