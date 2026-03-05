from pathlib import Path

from skill_guard.models import CheckResult, ConflictResult, ValidationResult
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
    assert "skill-gate conflict" in md
