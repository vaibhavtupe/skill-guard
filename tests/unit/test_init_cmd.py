from typer.testing import CliRunner

from skill_guard.main import app

runner = CliRunner()


def test_init_cmd_creates_config(tmp_path):
    result = runner.invoke(app, ["init", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "skill-gate.yaml").exists()
