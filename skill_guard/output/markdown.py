"""Markdown output formatter (Phase 1: basic tables)."""

from __future__ import annotations

from typing import Any

from skill_guard.models import CheckRunReport, ConflictResult, SecurityResult, ValidationResult


def format_as_markdown(result: Any, command: str = "") -> str:
    if isinstance(result, ValidationResult):
        return _validation_md(result)
    if isinstance(result, SecurityResult):
        return _security_md(result)
    if isinstance(result, ConflictResult):
        return _conflict_md(result)
    if isinstance(result, CheckRunReport):
        return _check_run_md(result)
    return f"## skill-guard result\n\n``\n{result}\n``"


def _validation_md(result: ValidationResult) -> str:
    base_rows = []
    spec_rows = []
    for check in result.checks:
        status = "✅" if check.passed else ("⚠️" if check.severity == "warning" else "❌")
        row = f"| {check.check_name} | {status} {check.message} |"
        if check.message.startswith("[anthropic-spec]"):
            spec_rows.append(row)
        else:
            base_rows.append(row)

    rendered = (
        f"## skill-guard validate — `{result.skill_name}`\n\n"
        f"| Check | Result |\n|---|---|\n"
        + "\n".join(base_rows)
        + f"\n\n**Score:** {result.score}/100 (Grade {result.grade}) | "
        f"Blockers: {result.blockers} | Warnings: {result.warnings}\n"
    )
    if spec_rows:
        rendered += (
            "\n## Anthropic Spec\n\n| Check | Result |\n|---|---|\n" + "\n".join(spec_rows) + "\n"
        )
    return rendered


def _security_md(result: SecurityResult) -> str:
    rows = []
    for f in result.findings:
        status = "✅" if f.suppressed else "❌"
        rows.append(
            f"| {f.severity} | {status} {f.category} [{f.id}] | {f.file}:{f.line} | {f.description} |"
        )

    if not rows:
        rows.append("| - | ✅ No findings | - | - |")

    return (
        f"## skill-guard secure — `{result.skill_name}`\n\n"
        f"| Severity | Finding | Location | Description |\n|---|---|---|---|\n" + "\n".join(rows)
    )


def _conflict_md(result: ConflictResult) -> str:
    rows = []
    for m in result.matches:
        status = "❌" if m.severity == "high" else "⚠️"
        rows.append(f"| {m.existing_skill_name} | {status} {m.severity} | {m.similarity_score} |")

    if not rows:
        rows.append("| - | ✅ No conflicts | - |")

    return (
        f"## skill-guard conflict — `{result.skill_name}`\n\n"
        f"| Skill | Severity | Score |\n|---|---|---|\n" + "\n".join(rows)
    )


def _check_run_md(result: CheckRunReport) -> str:
    rows = []
    for skill in result.skills:
        rows.append(
            f"| {skill.skill_name} | {skill.target_status} | {skill.validation} | "
            f"{skill.security} | {skill.conflict} | {skill.test} | {skill.status} |"
        )

    if not rows:
        rows.append("| - | - | - | - | - | - | passed |")

    return (
        "## skill-guard check\n\n"
        f"- mode: {result.mode}\n"
        f"- target_root: {result.target_root}\n"
        f"- against: {result.against}\n"
        f"- total_skills: {result.total_skills}\n"
        f"- checked_skills: {result.checked_skills}\n"
        f"- skipped_skills: {result.skipped_skills}\n"
        f"- passed: {result.passed}\n"
        f"- warnings: {result.warnings}\n"
        f"- failed: {result.failed}\n"
        f"- status: {result.status}\n"
        f"- summary: {result.summary}\n\n"
        "| Skill | Change | Validation | Security | Conflict | Test | Status |\n"
        "|---|---|---|---|---|---|---|\n" + "\n".join(rows)
    )
