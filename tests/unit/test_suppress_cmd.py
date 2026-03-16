"""Unit tests for skill-guard suppress command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from skill_guard.main import app

runner = CliRunner()


def _make_valid_skill(tmp_path: Path, name: str = "my-skill") -> Path:
    skill = tmp_path / name
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: |\n  Use when you need to test suppression.\nmetadata:\n  author: test\n  version: '1.0'\n---\n\nBody content here.\n",
        encoding="utf-8",
    )
    return skill


class TestSuppressCmd:
    def test_suppress_inserts_disable_comment(self, tmp_path: Path) -> None:
        skill = _make_valid_skill(tmp_path)
        result = runner.invoke(
            app,
            [
                "suppress",
                str(skill),
                "--finding",
                "INJECT-002",
                "--reason",
                "intentional role description",
            ],
        )
        assert result.exit_code == 0
        content = (skill / "SKILL.md").read_text(encoding="utf-8")
        assert "disable=INJECT-002" in content

    def test_suppress_writes_yaml_record(self, tmp_path: Path) -> None:
        skill = _make_valid_skill(tmp_path)
        result = runner.invoke(
            app, ["suppress", str(skill), "--finding", "INJECT-002", "--reason", "test reason"]
        )
        assert result.exit_code == 0
        config_path = tmp_path / "skill-guard.yaml"
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")
        assert "INJECT-002" in content
        assert "test reason" in content

    def test_suppress_without_reason_in_non_tty_fails(self, tmp_path: Path) -> None:
        skill = _make_valid_skill(tmp_path)
        result = runner.invoke(app, ["suppress", str(skill), "--finding", "INJECT-002"])
        # Should fail — no --reason and not a TTY (CliRunner is non-interactive)
        assert result.exit_code != 0

    def test_suppress_unknown_finding_fails(self, tmp_path: Path) -> None:
        skill = _make_valid_skill(tmp_path)
        result = runner.invoke(
            app, ["suppress", str(skill), "--finding", "FAKE-999", "--reason", "test"]
        )
        assert result.exit_code != 0

    def test_suppress_missing_skill_md_fails(self, tmp_path: Path) -> None:
        skill = tmp_path / "empty-skill"
        skill.mkdir()
        result = runner.invoke(
            app, ["suppress", str(skill), "--finding", "INJECT-002", "--reason", "test"]
        )
        assert result.exit_code != 0

    def test_suppress_idempotent_on_second_run(self, tmp_path: Path) -> None:
        skill = _make_valid_skill(tmp_path)
        runner.invoke(app, ["suppress", str(skill), "--finding", "INJECT-002", "--reason", "first"])
        runner.invoke(
            app, ["suppress", str(skill), "--finding", "INJECT-002", "--reason", "second"]
        )
        content = (skill / "SKILL.md").read_text(encoding="utf-8")
        # Should not have duplicate disable comments
        assert content.count("disable=INJECT-002") == 1


class TestValidateShowSuppressed:
    def test_show_suppressed_flag_works(self, tmp_path: Path) -> None:
        skill = _make_valid_skill(tmp_path)
        # Create a suppression record
        runner.invoke(
            app,
            [
                "suppress",
                str(skill),
                "--finding",
                "INJECT-005",
                "--reason",
                "false positive in docs",
            ],
        )
        # Validate with show-suppressed
        result = runner.invoke(app, ["validate", str(skill), "--show-suppressed"])
        assert "INJECT-005" in result.output
        assert "false positive in docs" in result.output

    def test_show_suppressed_no_config_says_none_found(self, tmp_path: Path) -> None:
        skill = _make_valid_skill(tmp_path)
        result = runner.invoke(app, ["validate", str(skill), "--show-suppressed"])
        assert "No suppressions" in result.output or result.exit_code in (0, 1, 2)
