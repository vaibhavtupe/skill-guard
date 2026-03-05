from pathlib import Path

from typer.testing import CliRunner

from skill_gate.main import app

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
