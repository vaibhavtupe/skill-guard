import json
from pathlib import Path

from skill_guard.models import (
    CheckResult,
    CheckRunReport,
    CheckSkillReport,
    ConflictMatch,
    ConflictResult,
    SecurityFinding,
    SecurityResult,
    ValidationResult,
)
from skill_guard.output.json_out import format_as_json
from skill_guard.output.markdown import format_as_markdown


def test_json_output_roundtrip():
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
    out = format_as_json(val, command="validate")
    assert '"command": "validate"' in out


def test_markdown_output():
    conflict = ConflictResult(
        skill_name="x",
        matches=[],
        name_collision=False,
        passed=True,
        high_conflicts=0,
        medium_conflicts=0,
    )
    md = format_as_markdown(conflict, command="conflict")
    assert "skill-guard conflict" in md


def test_json_output_supports_aggregate_check_report():
    report = CheckRunReport(
        mode="changed",
        target_root=Path("/tmp/skills"),
        against=Path("/tmp/skills"),
        total_skills=2,
        checked_skills=1,
        skipped_skills=1,
        passed=1,
        warnings=0,
        failed=0,
        status="passed",
        summary="1 skill checked, 1 skipped.",
        skills=[
            CheckSkillReport(
                skill_name="alpha",
                skill_path=Path("/tmp/skills/alpha"),
                target_status="modified",
                validation="passed",
                security="passed",
                conflict="passed",
                test="skipped",
                status="passed",
                summary="All blocking checks passed.",
            ),
            CheckSkillReport(
                skill_name="beta",
                skill_path=Path("/tmp/skills/beta"),
                target_status="deleted",
                validation="skipped",
                security="skipped",
                conflict="skipped",
                test="skipped",
                status="skipped",
                summary="Skill was deleted in the compared diff.",
            ),
        ],
    )

    out = format_as_json(report, command="check")
    payload = json.loads(out)

    assert payload["command"] == "check"
    assert payload["result"]["mode"] == "changed"
    assert payload["result"]["skills"][1]["target_status"] == "deleted"


def test_markdown_output_supports_aggregate_check_report():
    report = CheckRunReport(
        mode="changed",
        target_root=Path("/tmp/skills"),
        against=Path("/tmp/skills"),
        total_skills=1,
        checked_skills=1,
        skipped_skills=0,
        passed=1,
        warnings=0,
        failed=0,
        status="passed",
        summary="1 skill checked: 1 passed, 0 warning, 0 failed, 0 skipped.",
        skills=[
            CheckSkillReport(
                skill_name="alpha",
                skill_path=Path("/tmp/skills/alpha"),
                target_status="modified",
                validation="passed",
                security="passed",
                conflict="passed",
                test="skipped",
                status="passed",
                summary="All blocking checks passed.",
            )
        ],
    )

    md = format_as_markdown(report, command="check")

    assert "## skill-guard check" in md
    assert "| alpha | modified | passed | passed | passed | skipped | passed |" in md


def test_markdown_output_includes_remediation_and_status_summaries():
    validation = ValidationResult(
        skill_name="alpha",
        skill_path=Path("/tmp/alpha"),
        checks=[
            CheckResult(
                check_name="evals_directory_exists",
                passed=False,
                severity="warning",
                message="No evals/ directory found",
                suggestion="Create evals/evals.json.",
            )
        ],
        score=92,
        grade="A",
        passed=True,
        warnings=1,
        blockers=0,
    )
    security = SecurityResult(
        skill_name="alpha",
        findings=[
            SecurityFinding(
                id="URL-001",
                severity="medium",
                category="DATA_EXFILTRATION",
                file="scripts/setup.sh",
                line=2,
                pattern="https?://",
                matched_text="https://example.com",
                description="External URL found in script file",
                suggestion="Set secure.allow_external_urls_in_scripts: true when intentional.",
                suppressed=False,
            )
        ],
        passed=True,
        critical_count=0,
        high_count=0,
        medium_count=1,
        low_count=0,
    )
    conflict = ConflictResult(
        skill_name="alpha",
        matches=[
            ConflictMatch(
                existing_skill_name="beta",
                similarity_score=0.66,
                severity="medium",
                overlapping_phrases=["diagnose latency"],
                suggestions=["Add conflict_ignore in SKILL.md if this overlap is intentional"],
            )
        ],
        name_collision=False,
        passed=True,
        high_conflicts=0,
        medium_conflicts=1,
    )

    validation_md = format_as_markdown(validation, command="validate")
    security_md = format_as_markdown(security, command="secure")
    conflict_md = format_as_markdown(conflict, command="conflict")

    assert "→ Create evals/evals.json." in validation_md
    assert "Status: warnings only (non-blocking by default)" in validation_md
    assert "secure.allow_external_urls_in_scripts: true when intentional" in security_md
    assert "Status:** no blocking findings" in security_md
    assert "Add conflict_ignore in SKILL.md if this overlap is intentional" in conflict_md
    assert "Status:** warnings only" in conflict_md
