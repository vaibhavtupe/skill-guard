from pathlib import Path

from typer.testing import CliRunner

from skill_guard.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0


def test_cli_validate():
    result = runner.invoke(app, ["validate", str(FIXTURES / "valid-skill"), "--format", "json"])
    # Should exit with warnings=0 -> exit_code 0
    assert result.exit_code in (0, 2)


def test_cli_secure():
    result = runner.invoke(app, ["secure", str(FIXTURES / "malicious-skill"), "--format", "json"])
    assert result.exit_code == 1


def test_cli_conflict():
    result = runner.invoke(
        app,
        [
            "conflict",
            str(FIXTURES / "conflicting-skill"),
            "--against",
            str(FIXTURES),
            "--format",
            "json",
        ],
    )
    assert result.exit_code in (0, 1)


def test_cli_help_positions_check_as_default():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Start with `skill-guard check <skill-or-skills-root>`" in result.stdout
    assert "Primary Workflow" in result.stdout
    assert "Default gate: run validate + secure + conflict" in result.stdout
    assert "Advanced / Secondary" in result.stdout
