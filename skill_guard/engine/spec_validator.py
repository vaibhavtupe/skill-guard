"""Anthropic AgentSkills spec compliance checks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from skill_guard.models import Finding, ParsedSkill, RuleSet

_TRIGGER_HINT_PATTERNS = ("use when", "whenever", "make sure to use", "triggers on")
_CODE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_TEXT_REFERENCE_SUFFIXES = {".md", ".txt", ".yaml", ".json"}


def _finding(rule_id: str, severity: str, message: str, suggestion: str | None = None) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=message,
        suggestion=suggestion,
        rule_set=RuleSet.ANTHROPIC_SPEC,
    )


def check_required_frontmatter(parsed_skill: ParsedSkill) -> list[Finding]:
    findings: list[Finding] = []
    if not parsed_skill.metadata.name.strip():
        findings.append(
            _finding(
                "required_frontmatter.name",
                "blocker",
                "Missing required frontmatter field 'name'.",
                "Add a non-empty name field to SKILL.md frontmatter.",
            )
        )
    if not parsed_skill.metadata.description.strip():
        findings.append(
            _finding(
                "required_frontmatter.description",
                "blocker",
                "Missing required frontmatter field 'description'.",
                "Add a non-empty description field to SKILL.md frontmatter.",
            )
        )
    return findings


def check_skill_md_length(parsed_skill: ParsedSkill) -> list[Finding]:
    non_blank_lines = [line for line in parsed_skill.body.splitlines() if line.strip()]
    count = len(non_blank_lines)
    if count > 500:
        return [
            _finding(
                "skill_md_length.error",
                "blocker",
                f"SKILL.md body is {count} non-blank lines; keep it at 500 or fewer.",
                "Move detailed content into references/ or scripts/.",
            )
        ]
    if count > 400:
        return [
            _finding(
                "skill_md_length.warning",
                "warning",
                f"SKILL.md body is {count} non-blank lines; consider keeping it under 400.",
                "Trim the body or move large reference content into references/.",
            )
        ]
    return []


def check_description_quality(parsed_skill: ParsedSkill) -> list[Finding]:
    findings: list[Finding] = []
    description = parsed_skill.metadata.description.strip()

    if len(description.split()) < 20:
        findings.append(
            _finding(
                "description_quality.length",
                "warning",
                "Description is under 20 words; make the trigger conditions more explicit.",
                "Expand the description with scope, trigger, and constraints.",
            )
        )

    if description and not any(
        pattern in description.lower() for pattern in _TRIGGER_HINT_PATTERNS
    ):
        findings.append(
            _finding(
                "description_quality.trigger_hint",
                "info",
                "Description does not include an explicit trigger phrase like 'Use when'.",
                "Add a trigger-oriented phrase so the agent knows when to invoke the skill.",
            )
        )

    return findings


def check_code_in_body(parsed_skill: ParsedSkill) -> list[Finding]:
    findings: list[Finding] = []
    for match in _CODE_BLOCK_RE.finditer(parsed_skill.body):
        code_lines = [line for line in match.group(1).splitlines() if line.strip()]
        if len(code_lines) > 20:
            findings.append(
                _finding(
                    "body_code_block.length",
                    "warning",
                    f"Found a fenced code block with {len(code_lines)} non-blank lines in SKILL.md.",
                    "Move large code samples into scripts/.",
                )
            )
    return findings


def check_evals_json(skill_path: Path) -> list[Finding]:
    evals_dir = skill_path / "evals"
    evals_json = evals_dir / "evals.json"
    if not evals_dir.is_dir():
        return []

    if not evals_json.is_file():
        return [
            _finding(
                "evals_json.missing",
                "warning",
                "evals/ exists but evals/evals.json is missing.",
                "Add evals/evals.json with skill_name and evals keys.",
            )
        ]

    try:
        payload = json.loads(evals_json.read_text(encoding="utf-8"))
    except Exception:
        return [
            _finding(
                "evals_json.parse",
                "warning",
                "evals/evals.json exists but could not be parsed as JSON.",
                "Provide valid JSON with skill_name and evals keys.",
            )
        ]

    missing = [key for key in ("skill_name", "evals") if key not in payload]
    if not missing:
        return []

    return [
        _finding(
            "evals_json.keys",
            "warning",
            f"evals/evals.json is missing required key(s): {', '.join(missing)}.",
            "Ensure evals/evals.json includes both skill_name and evals.",
        )
    ]


def check_references_files(skill_path: Path) -> list[Finding]:
    references_dir = skill_path / "references"
    if not references_dir.is_dir():
        return []

    invalid = sorted(
        path.name
        for path in references_dir.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() not in _TEXT_REFERENCE_SUFFIXES
    )
    if not invalid:
        return []

    return [
        _finding(
            "references_files.binary",
            "warning",
            f"references/ contains binary or unsupported files: {', '.join(invalid)}.",
            "Keep references/ to .md, .txt, .yaml, or .json files.",
        )
    ]


def run_spec_validation(parsed_skill: ParsedSkill) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_required_frontmatter(parsed_skill))
    findings.extend(check_skill_md_length(parsed_skill))
    findings.extend(check_description_quality(parsed_skill))
    findings.extend(check_code_in_body(parsed_skill))
    findings.extend(check_evals_json(parsed_skill.path))
    findings.extend(check_references_files(parsed_skill.path))
    return findings
