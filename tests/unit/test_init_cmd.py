from pathlib import Path

from typer.testing import CliRunner

from skill_guard.config import ValidateConfig
from skill_guard.engine.quality import run_validation
from skill_guard.main import app
from skill_guard.parser import parse_skill

runner = CliRunner()


def test_init_cmd_creates_config(tmp_path):
    result = runner.invoke(app, ["init", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "skill-guard.yaml").exists()


def test_init_template_base_creates_expected_structure(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated-skill"

    result = runner.invoke(app, ["init", "--template", "base", "--output", str(output_dir)])

    assert result.exit_code == 0
    assert (output_dir / "SKILL.md").exists()
    assert (output_dir / "evals").is_dir()
    assert (output_dir / "references").is_dir()
    assert (output_dir / "scripts").is_dir()
    assert (output_dir / "assets").is_dir()


def test_generated_template_passes_validate_with_no_errors(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated-skill"
    result = runner.invoke(app, ["init", "--template", "base", "--output", str(output_dir)])

    assert result.exit_code == 0
    skill = parse_skill(output_dir)
    validation = run_validation(skill, ValidateConfig())
    assert validation.blockers == 0
    assert validation.warnings == 0


def test_init_list_templates_prints_available_templates() -> None:
    result = runner.invoke(app, ["init", "--list-templates"])

    assert result.exit_code == 0
    assert "Available templates:" in result.stdout
    assert "base" in result.stdout
    assert "weather-tool" in result.stdout
    assert "search-tool" in result.stdout


def test_init_template_refuses_to_overwrite_non_empty_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated-skill"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep", encoding="utf-8")

    result = runner.invoke(app, ["init", "--template", "base", "--output", str(output_dir)])

    assert result.exit_code != 0


def test_init_template_can_override_skill_name(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated-skill"

    result = runner.invoke(
        app,
        ["init", "--template", "base", "--output", str(output_dir), "--name", "custom-skill"],
    )

    assert result.exit_code == 0
    assert "custom-skill" in (output_dir / "SKILL.md").read_text(encoding="utf-8")
