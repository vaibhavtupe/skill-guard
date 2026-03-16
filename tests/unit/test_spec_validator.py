from __future__ import annotations

from pathlib import Path

from skill_guard.config import ValidateConfig
from skill_guard.engine.quality import run_validation
from skill_guard.engine.spec_validator import (
    check_code_in_body,
    check_description_quality,
    check_evals_json,
    check_references_files,
    check_required_frontmatter,
    check_skill_md_length,
    run_spec_validation,
)
from skill_guard.models import ParsedSkill, SkillMetadata
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def _parsed_skill(
    *,
    name: str = "sample-skill",
    description: str = "Use when this skill handles a specific repository workflow with enough detail for reliable triggering.",
    body: str = "# Body",
) -> ParsedSkill:
    return ParsedSkill(
        path=Path("/tmp/sample-skill"),
        skill_md_path=Path("/tmp/sample-skill/SKILL.md"),
        metadata=SkillMetadata(
            name=name, description=description, metadata={"author": "team", "version": "1.0"}
        ),
        body=body,
        body_line_count=len([line for line in body.splitlines() if line.strip()]),
        has_scripts=False,
        scripts=[],
        has_references=False,
        references=[],
        has_assets=False,
        has_evals=False,
        evals_config=None,
    )


def test_compliant_fixture_has_zero_spec_findings() -> None:
    skill = parse_skill(FIXTURES / "anthropic-compliant")

    findings = run_spec_validation(skill)

    assert findings == []


def test_missing_name_returns_error() -> None:
    findings = check_required_frontmatter(_parsed_skill(name=""))

    assert any(f.severity == "blocker" and "name" in f.message for f in findings)


def test_missing_description_returns_error() -> None:
    findings = check_required_frontmatter(_parsed_skill(description=""))

    assert any(f.severity == "blocker" and "description" in f.message for f in findings)


def test_description_under_20_words_returns_warning() -> None:
    findings = check_description_quality(
        _parsed_skill(description="Too short to be specific here.")
    )

    assert any(f.severity == "warning" for f in findings)


def test_description_with_use_when_has_no_trigger_info_finding() -> None:
    findings = check_description_quality(
        _parsed_skill(
            description="Use when this skill needs to be selected for a precise repository review workflow with clear operating constraints and expected outcomes."
        )
    )

    assert not any(f.severity == "info" and "trigger phrase" in f.message for f in findings)


def test_body_over_500_lines_returns_error() -> None:
    findings = check_skill_md_length(_parsed_skill(body="\n".join(f"line {i}" for i in range(501))))

    assert any(f.severity == "blocker" for f in findings)


def test_body_over_400_lines_returns_warning() -> None:
    findings = check_skill_md_length(_parsed_skill(body="\n".join(f"line {i}" for i in range(401))))

    assert any(f.severity == "warning" for f in findings)


def test_body_under_400_lines_returns_no_findings() -> None:
    findings = check_skill_md_length(_parsed_skill(body="\n".join(f"line {i}" for i in range(400))))

    assert findings == []


def test_malformed_evals_json_returns_warning(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    (skill_dir / "evals").mkdir(parents=True)
    (skill_dir / "evals" / "evals.json").write_text("{not json", encoding="utf-8")

    findings = check_evals_json(skill_dir)

    assert any(f.severity == "warning" for f in findings)


def test_missing_evals_json_returns_warning(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    (skill_dir / "evals").mkdir(parents=True)

    findings = check_evals_json(skill_dir)

    assert any("missing" in f.message for f in findings)


def test_evals_json_missing_required_keys_returns_warning() -> None:
    findings = check_evals_json(FIXTURES / "anthropic-noncompliant")

    assert any(f.severity == "warning" and "skill_name" in f.message for f in findings)


def test_binary_reference_file_returns_warning() -> None:
    findings = check_references_files(FIXTURES / "anthropic-noncompliant")

    assert any(f.severity == "warning" and "blob.bin" in f.message for f in findings)


def test_large_code_block_returns_warning() -> None:
    body = "```python\n" + "\n".join(f"print({i})" for i in range(21)) + "\n```"

    findings = check_code_in_body(_parsed_skill(body=body))

    assert any(f.severity == "warning" for f in findings)


def test_anthropic_spec_false_in_config_skips_spec_findings() -> None:
    skill = parse_skill(FIXTURES / "anthropic-noncompliant")

    result = run_validation(
        skill,
        ValidateConfig(
            anthropic_spec=False,
            require_author_in_metadata=False,
            require_version_in_metadata=False,
        ),
    )

    assert not any(check.message.startswith("[anthropic-spec]") for check in result.checks)
