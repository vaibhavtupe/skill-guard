"""Text output formatter using rich."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from skill_guard.models import ConflictResult, SecurityResult, ValidationResult
from skill_guard.output.semantics import (
    conflict_trust_state,
    security_trust_state,
    trust_state_label,
    validation_trust_state,
)

console = Console()


def format_validation_result(
    result: ValidationResult, quiet: bool = False, verbose: bool = False
) -> None:
    base_checks = [
        check for check in result.checks if not check.message.startswith("[anthropic-spec]")
    ]
    spec_checks = [check for check in result.checks if check.message.startswith("[anthropic-spec]")]

    _print_validation_table(
        title=f"skill-guard validate — {result.skill_name}",
        checks=base_checks,
        quiet=quiet,
        verbose=verbose,
    )
    if spec_checks:
        _print_validation_table(
            title="Anthropic Spec",
            checks=spec_checks,
            quiet=quiet,
            verbose=verbose,
        )

    console.print(
        f"Score: {result.score}/100 | Grade: {result.grade} | "
        f"Blockers: {result.blockers} | Warnings: {result.warnings} | "
        f"Status: {_validation_status_label(result)} | "
        f"Trust state: {trust_state_label(validation_trust_state(result))}"
    )


def _print_validation_table(*, title: str, checks: list, quiet: bool, verbose: bool) -> None:
    table = Table(title=title)
    table.add_column("Check")
    table.add_column("Result")

    for check in checks:
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


def format_security_result(result: SecurityResult, quiet: bool = False) -> None:
    table = Table(title=f"skill-guard secure — {result.skill_name}")
    table.add_column("Severity")
    table.add_column("Finding")

    visible_findings = [
        finding for finding in result.findings if not (quiet and finding.suppressed)
    ]
    if not visible_findings:
        table.add_row("✅ none", "No security findings detected")

    for finding in visible_findings:
        status = "✅" if finding.suppressed else "❌"
        msg = f"{finding.category} [{finding.id}] in {finding.file}:{finding.line}\n{finding.description}\n→ {finding.suggestion}"
        table.add_row(f"{status} {finding.severity}", msg)

    console.print(table)
    console.print(
        f"Critical: {result.critical_count} | High: {result.high_count} | "
        f"Medium: {result.medium_count} | Low: {result.low_count} | "
        f"Status: {_security_status_label(result)} | "
        f"Trust state: {trust_state_label(security_trust_state(result))}"
    )


def format_conflict_result(result: ConflictResult, quiet: bool = False) -> None:
    table = Table(title=f"skill-guard conflict — {result.skill_name}")
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

    if not result.name_collision and not result.matches:
        table.add_row("✅ none", "No conflicting skills detected")

    console.print(table)
    console.print(
        f"High conflicts: {result.high_conflicts} | Medium conflicts: {result.medium_conflicts} | "
        f"Status: {_conflict_status_label(result)} | "
        f"Trust state: {trust_state_label(conflict_trust_state(result))}"
    )


def _validation_status_label(result: ValidationResult) -> str:
    if result.blockers > 0:
        return "blocking failures"
    if result.warnings > 0:
        return "warnings only (non-blocking by default)"
    return "clean"


def _security_status_label(result: SecurityResult) -> str:
    if result.passed:
        if any(finding.suppressed for finding in result.findings):
            return "intentional exceptions present"
        return "no blocking findings"
    return "blocking findings present"


def _conflict_status_label(result: ConflictResult) -> str:
    if result.name_collision or result.high_conflicts > 0:
        return "blocking conflicts present"
    if result.medium_conflicts > 0:
        return "warnings only"
    return "clean"
