"""
Security scanner — regex-based pattern matching with suppression support.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from skill_gate.config import SecureConfig
from skill_gate.models import ParsedSkill, SecurityFinding, SecurityResult

# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityPattern:
    id: str
    category: str
    severity: str
    pattern: str
    description: str
    suggestion: str


SECURITY_PATTERNS: list[SecurityPattern] = [
    # CREDENTIALS — Critical
    SecurityPattern(
        id="CRED-001",
        category="CREDENTIALS",
        severity="critical",
        pattern=r"(?i)(api_key|apikey|api-key)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{20,}",
        description="Possible API key in plaintext",
        suggestion="Use environment variables: ${API_KEY}",
    ),
    SecurityPattern(
        id="CRED-002",
        category="CREDENTIALS",
        severity="critical",
        pattern=r"(?i)(password|passwd|secret)\s*[:=]\s*[\"'][^\"']{6,}[\"']",
        description="Possible hardcoded password",
        suggestion="Use environment variables",
    ),
    SecurityPattern(
        id="CRED-003",
        category="CREDENTIALS",
        severity="critical",
        pattern=r"(AKIA|AGPA|AIPA|ANPA|ANVA|AROA|ASCA|ASIA)[A-Z0-9]{16}",
        description="AWS Access Key ID pattern detected",
        suggestion="Remove credentials from skill files",
    ),
    # DANGEROUS EXEC — High
    SecurityPattern(
        id="EXEC-001",
        category="DANGEROUS_EXEC",
        severity="high",
        pattern=r"(curl|wget)\s+[^\|]+\|\s*(sh|bash|zsh|python|python3|eval)",
        description="Remote code download and execute pattern",
        suggestion="Download scripts separately, review before executing",
    ),
    SecurityPattern(
        id="EXEC-002",
        category="DANGEROUS_EXEC",
        severity="high",
        pattern=r"rm\s+-rf\s+[/~]",
        description="Destructive recursive delete from root or home",
        suggestion="Use explicit paths and add confirmation checks",
    ),
    SecurityPattern(
        id="EXEC-003",
        category="DANGEROUS_EXEC",
        severity="high",
        pattern=r"chmod\s+777",
        description="World-writable permissions",
        suggestion="Use minimal permissions (644 for files, 755 for executables)",
    ),
    # DATA EXFILTRATION — High
    SecurityPattern(
        id="EXFIL-001",
        category="DATA_EXFILTRATION",
        severity="high",
        pattern=r"(curl|wget)\s+.*\$\{?(HOME|USER|PATH|AWS|SECRET|TOKEN|KEY)",
        description="Possible environment variable exfiltration via HTTP",
        suggestion="Review what data is being sent to external endpoints",
    ),
    SecurityPattern(
        id="EXFIL-002",
        category="DATA_EXFILTRATION",
        severity="high",
        pattern=r"base64\s*[|>].*\s*(curl|wget|nc)",
        description="Base64-encoded data sent to network",
        suggestion="Review data being transmitted",
    ),
    # PROMPT INJECTION — Medium
    SecurityPattern(
        id="INJECT-001",
        category="PROMPT_INJECTION",
        severity="medium",
        pattern=r"<IMPORTANT>|IMPORTANT:.*ignore|ignore.*previous.*instructions",
        description="Possible prompt injection in skill description",
        suggestion="Remove meta-instructions from skill content",
    ),
    SecurityPattern(
        id="INJECT-002",
        category="PROMPT_INJECTION",
        severity="medium",
        pattern=r"[\u200b-\u200f\u202a-\u202e\ufeff]",
        description="Zero-width Unicode characters detected",
        suggestion="Remove invisible Unicode characters",
    ),
    # SCOPE — Medium
    SecurityPattern(
        id="SCOPE-001",
        category="SCOPE",
        severity="medium",
        pattern=r"Bash\s*\(\s*\*\s*\)",
        description="Overly broad Bash tool permission",
        suggestion="Restrict allowed-tools to specific commands",
    ),
]

_SUPPRESSION_RE = re.compile(r"skill-gate:\s*ignore\s+([A-Z]+-\d+)")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_security_scan(skill: ParsedSkill, config: SecureConfig) -> SecurityResult:
    """Scan skill files for dangerous patterns and return SecurityResult."""
    findings: list[SecurityFinding] = []

    files_to_scan = _gather_files(skill)

    # Build allow_list map (id -> list of allowed files or None)
    allow_list = {}
    for entry in config.allow_list:
        allow_list.setdefault(entry.id, set())
        if entry.file:
            allow_list[entry.id].add(entry.file)

    for file_path in files_to_scan:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Skip binary files
            continue
        except Exception:
            continue

        suppression_ids = _extract_suppressions(text)

        for pattern in SECURITY_PATTERNS:
            for match in re.finditer(pattern.pattern, text):
                line_no = text[: match.start()].count("\n") + 1
                matched_text = match.group(0)

                suppressed = False

                # Inline suppression
                if pattern.id in suppression_ids and pattern.severity in ("medium", "low"):
                    suppressed = True

                # Allow list suppression (even for high/critical)
                if pattern.id in allow_list:
                    allowed_files = allow_list[pattern.id]
                    if not allowed_files or str(file_path).endswith(tuple(allowed_files)):
                        suppressed = True

                findings.append(
                    SecurityFinding(
                        id=pattern.id,
                        severity=pattern.severity,  # type: ignore
                        category=pattern.category,  # type: ignore
                        file=str(file_path),
                        line=line_no,
                        pattern=pattern.pattern,
                        matched_text=_redact_if_credential(pattern.id, matched_text),
                        description=pattern.description,
                        suggestion=pattern.suggestion,
                        suppressed=suppressed,
                    )
                )

    # Counts (excluding suppressed for pass/fail logic)
    crit = sum(1 for f in findings if f.severity == "critical" and not f.suppressed)
    high = sum(1 for f in findings if f.severity == "high" and not f.suppressed)
    medium = sum(1 for f in findings if f.severity == "medium" and not f.suppressed)
    low = sum(1 for f in findings if f.severity == "low" and not f.suppressed)

    block_on = set(config.block_on)
    passed = True
    if "critical" in block_on and crit > 0:
        passed = False
    if "high" in block_on and high > 0:
        passed = False
    if "medium" in block_on and medium > 0:
        passed = False
    if "low" in block_on and low > 0:
        passed = False

    return SecurityResult(
        skill_name=skill.metadata.name,
        findings=findings,
        passed=passed,
        critical_count=crit,
        high_count=high,
        medium_count=medium,
        low_count=low,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gather_files(skill: ParsedSkill) -> list[Path]:
    files: list[Path] = [skill.skill_md_path]

    if skill.has_scripts:
        files.extend([p for p in skill.scripts if p.is_file()])

    if skill.has_references:
        files.extend([p for p in skill.references if p.is_file()])

    # Evals directory
    evals_dir = skill.path / "evals"
    if evals_dir.exists() and evals_dir.is_dir():
        for p in evals_dir.rglob("*"):
            if p.is_file():
                files.append(p)

    return files


def _extract_suppressions(text: str) -> set[str]:
    """Extract suppression IDs from inline comments."""
    return set(_SUPPRESSION_RE.findall(text))


def _redact_if_credential(pattern_id: str, matched_text: str) -> str:
    """Redact matched secrets for credential patterns."""
    if pattern_id.startswith("CRED"):
        if len(matched_text) <= 4:
            return "****"
        return matched_text[:4] + "****"
    return matched_text
