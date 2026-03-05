from pathlib import Path

from skill_gate.models import CheckResult, ConflictMatch, ConflictResult, SecurityFinding, SecurityResult, ValidationResult
from skill_gate.output.text import (
    format_conflict_result,
    format_security_result,
    format_validation_result,
)


def test_text_formatters_smoke():
    val = ValidationResult(
        skill_name="x",
        skill_path=Path("/tmp/x"),
        checks=[CheckResult(check_name="c", passed=True, severity="info", message="ok")],
        score=100,
        grade="A",
        passed=True,
        warnings=0,
        blockers=0,
    )
    sec = SecurityResult(
        skill_name="x",
        findings=[
            SecurityFinding(
                id="CRED-001",
                severity="critical",
                category="CREDENTIALS",
                file="SKILL.md",
                line=1,
                pattern="x",
                matched_text="abcd****",
                description="x",
                suggestion="y",
                suppressed=False,
            )
        ],
        passed=False,
        critical_count=1,
        high_count=0,
        medium_count=0,
        low_count=0,
    )
    conflict = ConflictResult(
        skill_name="x",
        matches=[
            ConflictMatch(
                existing_skill_name="y",
                similarity_score=0.8,
                severity="high",
                overlapping_phrases=["test"],
                suggestions=["merge"],
            )
        ],
        name_collision=False,
        passed=False,
        high_conflicts=1,
        medium_conflicts=0,
    )

    # Smoke tests (just ensure no exceptions)
    format_validation_result(val, quiet=True)
    format_security_result(sec, quiet=True)
    format_conflict_result(conflict)
