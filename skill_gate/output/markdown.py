"""Markdown output formatter (Phase 1: basic tables)."""

from __future__ import annotations

from typing import Any

from skill_gate.models import ConflictResult, SecurityResult, ValidationResult


def format_as_markdown(result: Any, command: str = "") -> str:
    if isinstance(result, ValidationResult):
        return _validation_md(result)
    if isinstance(result, SecurityResult):
        return _security_md(result)
    if isinstance(result, ConflictResult):
        return _conflict_md(result)
    return f"## skill-gate result\n\n``\n{result}\n``"


def _validation_md(result: ValidationResult) -> str:
    rows = []
    for check in result.checks:
        status = "✅" if check.passed else ("⚠️" if check.severity == "warning" else "❌")
        rows.append(f"| {check.check_name} | {status} {check.message} |")

    return (
        f"## skill-gate validate — `{result.skill_name}`\n\n"
        f"| Check | Result |\n|---|---|\n"
        + "\n".join(rows)
        + f"\n\n**Score:** {result.score}/100 (Grade {result.grade}) | "
        f"Blockers: {result.blockers} | Warnings: {result.warnings}\n"
    )


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
        f"## skill-gate secure — `{result.skill_name}`\n\n"
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
        f"## skill-gate conflict — `{result.skill_name}`\n\n"
        f"| Skill | Severity | Score |\n|---|---|---|\n" + "\n".join(rows)
    )
