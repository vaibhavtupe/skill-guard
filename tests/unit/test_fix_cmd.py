from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from skill_guard.config import ValidateConfig
from skill_guard.engine.quality import run_validation
from skill_guard.main import app
from skill_guard.parser import parse_skill

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_fix_command_repairs_fixable_skill_and_clears_repaired_findings(tmp_path: Path) -> None:
    skill_dir = tmp_path / "fixable-skill"
    shutil.copytree(FIXTURES / "fixable-skill", skill_dir)

    result = runner.invoke(app, ["fix", str(skill_dir)])

    assert result.exit_code == 0
    skill = parse_skill(skill_dir)
    validation = run_validation(
        skill,
        ValidateConfig(require_author_in_metadata=False),
    )
    repaired_checks = {check.check_name: check.passed for check in validation.checks}
    assert repaired_checks["name_field_present"] is True
    assert repaired_checks["description_field_present"] is True
    assert repaired_checks["metadata_has_version"] is True
    assert repaired_checks["no_broken_body_paths"] is True


def test_fix_command_skips_ambiguous_link_and_warns(tmp_path: Path) -> None:
    skill_dir = tmp_path / "ambiguous-skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "references" / "guide.md").write_text("guide", encoding="utf-8")
    (skill_dir / "scripts" / "guide.md").write_text("guide", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        '---\nname: ambiguous-skill\ndescription: |\n  Use when this skill handles a specific workflow with enough detail for selection.\nmetadata:\n  author: fix-team\n  version: "1.0"\n---\n\nSee [guide](guide.md).\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["fix", str(skill_dir)])

    assert result.exit_code == 0
    assert "manual fix" in result.stdout
    assert "broken relative links with multiple candidates are not auto-fixed" in result.stdout
    assert "[guide](guide.md)" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_fix_command_check_mode_is_non_destructive_and_non_zero(tmp_path: Path) -> None:
    skill_dir = tmp_path / "fixable-skill"
    shutil.copytree(FIXTURES / "fixable-skill", skill_dir)
    before = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    result = runner.invoke(app, ["fix", str(skill_dir), "--check"])

    assert result.exit_code == 1
    assert "would be applied" in result.stdout
    assert "0 fixes applied" not in result.stdout
    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == before
