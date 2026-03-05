"""Text output formatter using rich."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from skill_guard.models import ConflictResult, SecurityResult, ValidationResult

console = Console()


def format_validation_result(
    result: ValidationResult, quiet: bool = False, verbose: bool = False
) -> None:
    table = Table(title=f"skill-gate validate — {result.skill_name}")
    table.add_column("Check")
    table.add_column("Result")

    for check in result.checks:
        if quiet and check.passed:
            continue
        if not verbose and check.passed and check.severity == "info":
            continue

        status = "✅" if check.passed else ("⚠️" if check.severity == "warning" else "❌")
        msg = check.message
        if not check.passed and check.suggestion:
            msg += f"\n→ {check.suggestion}"
        table.add_row(check.check_name, f"{status} {msg}")

    console.print(table)
    console.print(
        f"Score: {result.score}/100 | Grade: {result.grade} | "
        f"Blockers: {result.blockers} | Warnings: {result.warnings}"
    )


def format_security_result(result: SecurityResult, quiet: bool = False) -> None:
    table = Table(title=f"skill-gate secure — {result.skill_name}")
    table.add_column("Severity")
    table.add_column("Finding")

    for finding in result.findings:
        if quiet and finding.suppressed:
            continue
        status = "✅" if finding.suppressed else "❌"
        msg = f"{finding.category} [{finding.id}] in {finding.file}:{finding.line}\n{finding.description}\n→ {finding.suggestion}"
        table.add_row(f"{status} {finding.severity}", msg)

    console.print(table)
    console.print(
        f"Critical: {result.critical_count} | High: {result.high_count} | "
        f"Medium: {result.medium_count} | Low: {result.low_count}"
    )


def format_conflict_result(result: ConflictResult, quiet: bool = False) -> None:
    table = Table(title=f"skill-gate conflict — {result.skill_name}")
    table.add_column("Match")
    table.add_column("Details")

    if result.name_collision:
        table.add_row("❌ name collision", f"Name collision with {result.name_collision_with}")

    for match in result.matches:
        status = "❌" if match.severity == "high" else "⚠️"
        details = (
            f"score={match.similarity_score}\n"
            f"overlap: {', '.join(match.overlapping_phrases) if match.overlapping_phrases else 'n/a'}\n"
            f"suggestions: {', '.join(match.suggestions)}"
        )
        table.add_row(f"{status} {match.existing_skill_name}", details)

    console.print(table)
    console.print(
        f"High conflicts: {result.high_conflicts} | Medium conflicts: {result.medium_conflicts}"
    )
