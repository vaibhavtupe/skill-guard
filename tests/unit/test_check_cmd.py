from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

import skill_guard.commands.check as check_cmd_module
from skill_guard.main import app
from skill_guard.models import AgentTestResult, CheckResult, ValidationResult

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
    assert "- status: passed" in result.stdout


def test_check_malicious_skill(tmp_path: Path) -> None:
    against_dir = tmp_path / "against"
    shutil.copytree(FIXTURES / "valid-skill", against_dir / "valid-skill")

    result = runner.invoke(
        app,
        ["check", str(FIXTURES / "malicious-skill"), "--against", str(against_dir)],
    )
    assert result.exit_code == 1
    assert "- security: failed" in result.stdout


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


def test_check_runs_agent_evals_when_endpoint_provided(tmp_path: Path, monkeypatch) -> None:
    against_dir = tmp_path / "against"
    shutil.copytree(FIXTURES / "valid-skill", against_dir / "valid-skill")
    calls = {"count": 0}

    async def fake_run_agent_tests(skill, test_config) -> AgentTestResult:
        calls["count"] += 1
        assert skill.metadata.name == "valid-skill"
        assert test_config.endpoint == "https://agent.test"
        return AgentTestResult(
            skill_name=skill.metadata.name,
            endpoint=test_config.endpoint or "",
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            pass_rate=1.0,
            results=[],
            total_time_seconds=0.0,
            avg_latency_ms=0.0,
            passed=True,
        )

    monkeypatch.setattr(check_cmd_module, "run_agent_tests", fake_run_agent_tests)

    result = runner.invoke(
        app,
        [
            "check",
            str(FIXTURES / "valid-skill"),
            "--against",
            str(against_dir),
            "--endpoint",
            "https://agent.test",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert calls["count"] == 1
    payload = json.loads(result.stdout)
    assert payload["result"]["test"] == "passed"
    assert payload["result"]["result"]["test"]["passed"] is True


def test_check_uses_ci_output_format_from_config_when_flag_omitted(tmp_path: Path) -> None:
    against_dir = tmp_path / "against"
    config_path = tmp_path / "skill-guard.yaml"
    shutil.copytree(FIXTURES / "valid-skill", against_dir / "valid-skill")
    config_path.write_text(
        (
            "ci:\n"
            "  output_format: json\n"
            "  post_pr_comment: false\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "check",
            str(FIXTURES / "valid-skill"),
            "--against",
            str(against_dir),
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "check"


def test_check_fail_on_warning_exits_one(tmp_path: Path, monkeypatch) -> None:
    against_dir = tmp_path / "against"
    config_path = tmp_path / "skill-guard.yaml"
    shutil.copytree(FIXTURES / "valid-skill", against_dir / "valid-skill")
    config_path.write_text(
        (
            "ci:\n"
            "  fail_on_warning: true\n"
            "  post_pr_comment: false\n"
            "  output_format: json\n"
        ),
        encoding="utf-8",
    )

    def fake_run_validation(skill, config):  # noqa: ARG001
        return ValidationResult(
            skill_name=skill.metadata.name,
            skill_path=skill.path,
            checks=[
                CheckResult(
                    check_name="warning-check",
                    passed=True,
                    severity="warning",
                    message="warning",
                )
            ],
            score=90,
            grade="A",
            passed=True,
            warnings=1,
            blockers=0,
        )

    monkeypatch.setattr(check_cmd_module, "run_validation", fake_run_validation)

    result = runner.invoke(
        app,
        [
            "check",
            str(FIXTURES / "valid-skill"),
            "--against",
            str(against_dir),
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["result"]["status"] == "failed"
