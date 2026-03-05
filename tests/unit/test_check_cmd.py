from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from skill_guard.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_check_valid_skill(tmp_path: Path) -> None:
    against_dir = tmp_path / "against"
    shutil.copytree(FIXTURES / "valid-skill", against_dir / "valid-skill")

    result = runner.invoke(
        app,
        ["check", str(FIXTURES / "valid-skill"), "--against", str(against_dir)],
    )
    assert result.exit_code == 0
    assert "status=passed" in result.stdout


def test_check_malicious_skill(tmp_path: Path) -> None:
    against_dir = tmp_path / "against"
    shutil.copytree(FIXTURES / "valid-skill", against_dir / "valid-skill")

    result = runner.invoke(
        app,
        ["check", str(FIXTURES / "malicious-skill"), "--against", str(against_dir)],
    )
    assert result.exit_code == 1
    assert "security=failed" in result.stdout


def test_check_with_format_json(tmp_path: Path) -> None:
    against_dir = tmp_path / "against"
    shutil.copytree(FIXTURES / "valid-skill", against_dir / "valid-skill")

    result = runner.invoke(
        app,
        [
            "check",
            str(FIXTURES / "valid-skill"),
            "--against",
            str(against_dir),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "check"
    assert payload["result"]["status"] == "passed"
