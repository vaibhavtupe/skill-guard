from pathlib import Path

from skill_guard.config import ValidateConfig
from skill_guard.engine.quality import run_validation
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_quality_valid_skill():
    skill = parse_skill(FIXTURES / "valid-skill")
    result = run_validation(skill, ValidateConfig())
    assert result.passed is True
    assert result.score >= 80
    assert result.grade in ("A", "B")


def test_quality_broken_refs():
    skill = parse_skill(FIXTURES / "broken-refs-skill")
    result = run_validation(skill, ValidateConfig())
    assert result.passed is False
    assert result.blockers >= 1


def test_quality_ignores_dotted_api_field_references_in_body(tmp_path: Path):
    skill_dir = tmp_path / "api-fields-skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "references" / "guide.md").write_text("guide", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        """---
name: api-fields-skill
description: "Use when validating API field references in skill bodies without treating them as repo paths."
metadata:
  author: test-author
  version: "1.0"
---

See references/guide.md for the real repo file.
Read `response.output_text` and reader.pages from the API response before continuing.
Also surface `pagination.total` in the response.
""",
        encoding="utf-8",
    )

    skill = parse_skill(skill_dir)
    result = run_validation(skill, ValidateConfig())
    broken_paths_check = next(
        check for check in result.checks if check.check_name == "no_broken_body_paths"
    )

    assert broken_paths_check.passed is True


def test_quality_still_flags_uppercase_plain_text_doc_references(tmp_path: Path):
    skill_dir = tmp_path / "missing-doc-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: missing-doc-skill
description: "Use when validating plain text document references in skill bodies."
metadata:
  author: test-author
  version: "1.0"
---

Read REFERENCE.md before proceeding.
""",
        encoding="utf-8",
    )

    skill = parse_skill(skill_dir)
    result = run_validation(skill, ValidateConfig())
    broken_paths_check = next(
        check for check in result.checks if check.check_name == "no_broken_body_paths"
    )

    assert broken_paths_check.passed is False
    assert "REFERENCE.md" in broken_paths_check.message
