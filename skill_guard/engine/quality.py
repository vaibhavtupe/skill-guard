"""
Quality scorer — runs format compliance and quality checks, produces a 0-100 score.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from skill_guard.config import ValidateConfig
from skill_guard.engine.spec_validator import run_spec_validation
from skill_guard.models import CheckResult, Grade, ParsedSkill, ValidationResult

# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

_TRIGGER_HINT_RE = re.compile(r"use when", re.IGNORECASE)
_NAME_FORMAT_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$")
_RELATIVE_PATH_RE = re.compile(r"\]\(([^http][^)]+)\)|`([^`]+\.[a-z]{2,5})`")

_DEFAULT_VAGUE_PHRASES = [
    "a useful skill",
    "does helpful things",
    "helps with",
    "this skill",
    "a skill that",
    "a tool that",
    "useful for",
    "does things",
    "general purpose",
]


@dataclass
class _Check:
    name: str
    severity: str  # "blocker" | "warning" | "info"
    weight: int


_CHECKS: list[_Check] = [
    _Check("skill_md_exists", "blocker", 10),
    _Check("valid_yaml_frontmatter", "blocker", 10),
    _Check("name_field_present", "blocker", 10),
    _Check("description_field_present", "blocker", 10),
    _Check("directory_name_matches", "blocker", 8),
    _Check("name_format_valid", "blocker", 8),
    _Check("description_min_length", "warning", 5),
    _Check("description_max_length", "warning", 3),
    _Check("description_trigger_hint", "warning", 5),
    _Check("description_not_generic", "warning", 6),
    _Check("body_not_empty", "warning", 5),
    _Check("body_under_max_lines", "warning", 3),
    _Check("scripts_executable", "warning", 7),
    _Check("references_exist", "blocker", 8),
    _Check("no_broken_body_paths", "blocker", 8),
    _Check("evals_directory_exists", "warning", 4),
    _Check("metadata_has_author", "warning", 4),
    _Check("metadata_has_version", "warning", 4),
]

_TOTAL_WEIGHT = sum(c.weight for c in _CHECKS)
_CHECK_MAP = {c.name: c for c in _CHECKS}


def _grade_from_score(score: int) -> Grade:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_validation(skill: ParsedSkill, config: ValidateConfig) -> ValidationResult:
    """
    Run all validation checks and return a ValidationResult.

    Args:
        skill:  Parsed skill object.
        config: ValidateConfig with thresholds and toggles.

    Returns:
        ValidationResult with score, grade, and per-check results.
    """
    vague_phrases = _DEFAULT_VAGUE_PHRASES + list(config.vague_phrases or [])
    checks: list[CheckResult] = []

    # ── FORMAT CHECKS (blockers) ────────────────────────────────────────────

    # skill_md_exists — parser already guarantees this, but report it as passing
    checks.append(_pass("skill_md_exists", "SKILL.md found"))

    # valid_yaml_frontmatter — guaranteed by parser
    checks.append(_pass("valid_yaml_frontmatter", "Valid YAML frontmatter"))

    # name_field_present
    if skill.metadata.name:
        checks.append(_pass("name_field_present", f"name: {skill.metadata.name}"))
    else:
        checks.append(
            _fail("name_field_present", "Missing 'name' field", "Add: name: your-skill-name")
        )

    # description_field_present
    if skill.metadata.description:
        checks.append(_pass("description_field_present", "description field present"))
    else:
        checks.append(
            _fail(
                "description_field_present",
                "Missing 'description' field",
                'Add: description: "What this skill does. Use when..."',
            )
        )

    # directory_name_matches
    dir_name = skill.path.name
    skill_name = skill.metadata.name
    if dir_name == skill_name:
        checks.append(
            _pass("directory_name_matches", f"Directory name '{dir_name}' matches skill name")
        )
    else:
        checks.append(
            _fail(
                "directory_name_matches",
                f"Directory name '{dir_name}' does not match skill name '{skill_name}'",
                f"Rename the directory to '{skill_name}' or update the name field",
            )
        )

    # name_format_valid
    if _NAME_FORMAT_RE.match(skill_name or ""):
        checks.append(_pass("name_format_valid", f"Name '{skill_name}' uses valid characters"))
    else:
        checks.append(
            _fail(
                "name_format_valid",
                f"Name '{skill_name}' contains invalid characters",
                "Use only lowercase letters (a-z), digits (0-9), and hyphens. "
                "Must start and end with alphanumeric character.",
            )
        )

    # ── QUALITY CHECKS (warnings, configurable) ─────────────────────────────

    desc = skill.metadata.description or ""

    # description_min_length
    if len(desc) >= config.min_description_length:
        checks.append(
            _pass(
                "description_min_length",
                f"Description length {len(desc)} chars >= {config.min_description_length}",
            )
        )
    else:
        checks.append(
            _warn(
                "description_min_length",
                f"Description too short ({len(desc)} chars, minimum {config.min_description_length})",
                "Expand the description to clearly explain when this skill should be used",
            )
        )

    # description_max_length
    if len(desc) <= config.max_description_length:
        checks.append(
            _pass(
                "description_max_length",
                f"Description length {len(desc)} chars <= {config.max_description_length}",
            )
        )
    else:
        checks.append(
            _warn(
                "description_max_length",
                f"Description too long ({len(desc)} chars, maximum {config.max_description_length})",
                "Shorten the description. Move detailed content to references/ or the body",
            )
        )

    # description_trigger_hint
    if not config.require_trigger_hint or _TRIGGER_HINT_RE.search(desc):
        checks.append(
            _pass("description_trigger_hint", "Description contains trigger hint ('Use when')")
        )
    else:
        checks.append(
            _warn(
                "description_trigger_hint",
                "Description missing trigger hint",
                "Add a 'Use when...' phrase to help the agent know when to activate this skill",
            )
        )

    # description_not_generic
    desc_lower = desc.lower()
    found_vague = [p for p in vague_phrases if p.lower() in desc_lower]
    if not found_vague:
        checks.append(_pass("description_not_generic", "Description is specific and informative"))
    else:
        checks.append(
            _warn(
                "description_not_generic",
                f"Description contains generic phrases: {', '.join(repr(p) for p in found_vague)}",
                "Be specific about what this skill does and when to use it",
            )
        )

    # body_not_empty
    if skill.body.strip():
        checks.append(_pass("body_not_empty", "SKILL.md body has content"))
    else:
        checks.append(
            _warn(
                "body_not_empty",
                "SKILL.md body is empty",
                "Add instructions that tell the agent how to use this skill",
            )
        )

    # body_under_max_lines
    if skill.body_line_count <= config.max_body_lines:
        checks.append(
            _pass(
                "body_under_max_lines",
                f"Body length {skill.body_line_count} lines <= {config.max_body_lines}",
            )
        )
    else:
        checks.append(
            _warn(
                "body_under_max_lines",
                f"Body is {skill.body_line_count} lines (exceeds {config.max_body_lines} recommendation)",
                "Move detailed reference content to references/ directory",
            )
        )

    # scripts_executable
    non_exec = _find_non_executable_scripts(skill.scripts)
    if not skill.has_scripts or not non_exec:
        checks.append(
            _pass(
                "scripts_executable",
                f"{len(skill.scripts)} script(s) all executable"
                if skill.has_scripts
                else "No scripts",
            )
        )
    else:
        checks.append(
            _warn(
                "scripts_executable",
                f"{len(non_exec)} script(s) not executable: {', '.join(p.name for p in non_exec)}",
                f"Run: chmod +x {' '.join(str(p) for p in non_exec)}",
            )
        )

    # references_exist (BLOCKER)
    missing_refs = _find_missing_references(skill.references)
    if not skill.has_references or not missing_refs:
        checks.append(
            CheckResult(
                check_name="references_exist",
                passed=True,
                severity="blocker",
                message=f"{len(skill.references)} reference file(s) all exist"
                if skill.has_references
                else "No references directory",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_name="references_exist",
                passed=False,
                severity="blocker",
                message=f"Missing reference files: {', '.join(p.name for p in missing_refs)}",
                suggestion="Create the missing files or remove the references from SKILL.md",
            )
        )

    # no_broken_body_paths (BLOCKER)
    broken_paths = _find_broken_body_paths(skill.body, skill.path)
    if not broken_paths:
        checks.append(
            CheckResult(
                check_name="no_broken_body_paths",
                passed=True,
                severity="blocker",
                message="No broken relative paths in SKILL.md body",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_name="no_broken_body_paths",
                passed=False,
                severity="blocker",
                message=f"Broken relative paths in body: {', '.join(broken_paths)}",
                suggestion="Fix the paths or remove the references",
            )
        )

    # evals_directory_exists
    evals_severity = "blocker" if config.require_evals else "warning"
    if skill.has_evals:
        checks.append(
            CheckResult(
                check_name="evals_directory_exists",
                passed=True,
                severity=evals_severity,
                message=f"evals/ directory found with {len(skill.evals_config.tests) if skill.evals_config else 0} test(s)",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_name="evals_directory_exists",
                passed=False,
                severity=evals_severity,
                message="No evals/ directory found",
                suggestion=(
                    "Create evals/evals.json (preferred) or evals/config.yaml with test cases. "
                    "Required for integration testing (skill-guard test). "
                    "See docs/eval-authoring-guide.md"
                ),
            )
        )

    # metadata_has_author
    author_severity = "blocker" if config.require_author_in_metadata else "warning"
    if skill.metadata.author:
        checks.append(
            CheckResult(
                check_name="metadata_has_author",
                passed=True,
                severity=author_severity,
                message=f"author: {skill.metadata.author}",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_name="metadata_has_author",
                passed=False,
                severity=author_severity,
                message="Missing 'author' in metadata",
                suggestion="Add metadata:\\n  author: your-team-name",
            )
        )

    # metadata_has_version
    version_severity = "blocker" if config.require_version_in_metadata else "warning"
    if skill.metadata.version:
        checks.append(
            CheckResult(
                check_name="metadata_has_version",
                passed=True,
                severity=version_severity,
                message=f"version: {skill.metadata.version}",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_name="metadata_has_version",
                passed=False,
                severity=version_severity,
                message="Missing 'version' in metadata",
                suggestion='Add metadata:\\n  version: "1.0"',
            )
        )

    if config.anthropic_spec:
        for finding in run_spec_validation(skill):
            checks.append(
                CheckResult(
                    check_name=f"anthropic_spec.{finding.rule_id}",
                    passed=False,
                    severity=finding.severity,
                    message=f"[anthropic-spec] {finding.message}",
                    suggestion=finding.suggestion,
                )
            )

    # ── Compute score ───────────────────────────────────────────────────────
    check_result_map = {c.check_name: c for c in checks}
    passed_weight = sum(
        _CHECK_MAP[c.name].weight
        for c in _CHECKS
        if check_result_map.get(c.name) and check_result_map[c.name].passed
    )
    score = round((passed_weight / _TOTAL_WEIGHT) * 100)
    grade = _grade_from_score(score)

    blockers = sum(1 for c in checks if not c.passed and c.severity == "blocker")
    warnings = sum(1 for c in checks if not c.passed and c.severity == "warning")
    passed = blockers == 0

    return ValidationResult(
        skill_name=skill.metadata.name,
        skill_path=skill.path,
        checks=checks,
        score=score,
        grade=grade,
        passed=passed,
        warnings=warnings,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pass(check_name: str, message: str) -> CheckResult:
    return CheckResult(
        check_name=check_name,
        passed=True,
        severity=_CHECK_MAP[check_name].severity,
        message=message,
    )


def _fail(check_name: str, message: str, suggestion: str | None = None) -> CheckResult:
    return CheckResult(
        check_name=check_name,
        passed=False,
        severity="blocker",
        message=message,
        suggestion=suggestion,
    )


def _warn(check_name: str, message: str, suggestion: str | None = None) -> CheckResult:
    return CheckResult(
        check_name=check_name,
        passed=False,
        severity="warning",
        message=message,
        suggestion=suggestion,
    )


def _find_non_executable_scripts(scripts: list[Path]) -> list[Path]:
    """Return scripts that are not executable."""
    result = []
    for script in scripts:
        if script.name.startswith("."):
            continue
        if script.is_file() and not os.access(script, os.X_OK):
            result.append(script)
    return result


def _find_missing_references(references: list[Path]) -> list[Path]:
    """Return reference paths that don't exist on disk."""
    return [ref for ref in references if not ref.exists()]


def _is_plain_text_relative_path(raw_path: str) -> bool:
    """Heuristically keep plain-text path detection to explicit file references."""
    normalized = raw_path.strip()
    if "/" in normalized or normalized.startswith(("./", "../")):
        return True

    basename = Path(normalized).stem
    return bool(basename) and basename.upper() == basename and any(ch.isalpha() for ch in basename)


def _find_broken_body_paths(body: str, skill_path: Path) -> list[str]:
    """Find relative paths referenced in SKILL.md body that don't exist."""
    broken = []

    # 1) Markdown links and inline code
    for match in _RELATIVE_PATH_RE.finditer(body):
        raw_path = match.group(1) or match.group(2)
        if not raw_path or raw_path.startswith("http") or raw_path.startswith("#"):
            continue
        if "." not in raw_path and "/" not in raw_path:
            continue
        if not _is_plain_text_relative_path(raw_path):
            continue
        candidate = skill_path / raw_path
        if not candidate.exists():
            broken.append(raw_path)

    # 2) Plain text file paths like references/foo.md or scripts/bar.sh
    plain_paths = re.findall(r"(?:^|\s)([\w\-./]+\.[a-zA-Z0-9]{2,5})", body)
    for raw_path in plain_paths:
        raw_path = raw_path.strip()
        if raw_path.startswith("http") or raw_path.startswith("#"):
            continue
        if not _is_plain_text_relative_path(raw_path):
            continue
        candidate = skill_path / raw_path
        if not candidate.exists() and raw_path not in broken:
            broken.append(raw_path)

    return broken
