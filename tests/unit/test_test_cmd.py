from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from skill_guard.main import app
from skill_guard.models import (
    AgentTestComparisonResult,
    AgentTestResult,
    EvalTestComparison,
    EvalTestResult,
    HealthCheckTimeoutError,
    HookError,
)

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_test_cmd_exits_zero_when_all_tests_pass(monkeypatch) -> None:
    async def fake_run_agent_tests(skill, config):  # noqa: ARG001
        return AgentTestResult(
            skill_name="valid-skill",
            endpoint="https://mock-agent.test",
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            pass_rate=1.0,
            results=[
                EvalTestResult(
                    test_name="basic",
                    passed=True,
                    prompt="prompt",
                    response_text="diagnostic latency",
                    latency_ms=42,
                    checks_passed=["contains:diagnostic"],
                    checks_failed=[],
                    skill_triggered="valid-skill",
                    tool_calls=["valid-skill"],
                )
            ],
            total_time_seconds=0.1,
            avg_latency_ms=42.0,
            passed=True,
        )

    monkeypatch.setattr("skill_guard.commands.test.run_agent_tests", fake_run_agent_tests)
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
        ],
    )
    assert result.exit_code == 0
    assert "status=passed" in result.stdout


def test_test_cmd_exits_one_when_pass_rate_below_one(monkeypatch) -> None:
    async def fake_run_agent_tests(skill, config):  # noqa: ARG001
        return AgentTestResult(
            skill_name="valid-skill",
            endpoint="https://mock-agent.test",
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            pass_rate=0.0,
            results=[
                EvalTestResult(
                    test_name="basic",
                    passed=False,
                    prompt="prompt",
                    response_text="error",
                    latency_ms=250,
                    checks_passed=[],
                    checks_failed=["contains:diagnostic"],
                    skill_triggered=None,
                    tool_calls=[],
                )
            ],
            total_time_seconds=0.1,
            avg_latency_ms=250.0,
            passed=False,
        )

    monkeypatch.setattr("skill_guard.commands.test.run_agent_tests", fake_run_agent_tests)
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
        ],
    )
    assert result.exit_code == 1
    assert "status=failed" in result.stdout


def test_test_cmd_json_output(monkeypatch) -> None:
    async def fake_run_agent_tests(skill, config):  # noqa: ARG001
        return AgentTestResult(
            skill_name="valid-skill",
            endpoint="https://mock-agent.test",
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            pass_rate=1.0,
            results=[],
            total_time_seconds=0.1,
            avg_latency_ms=12.0,
            passed=True,
        )

    monkeypatch.setattr("skill_guard.commands.test.run_agent_tests", fake_run_agent_tests)
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert '"command": "test"' in result.stdout


def test_test_cmd_markdown_output(monkeypatch) -> None:
    async def fake_run_agent_tests(skill, config):  # noqa: ARG001
        return AgentTestResult(
            skill_name="valid-skill",
            endpoint="https://mock-agent.test",
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            pass_rate=1.0,
            results=[],
            total_time_seconds=0.1,
            avg_latency_ms=12.0,
            passed=True,
        )

    monkeypatch.setattr("skill_guard.commands.test.run_agent_tests", fake_run_agent_tests)
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
            "--format",
            "md",
        ],
    )
    assert result.exit_code == 0
    assert "## skill-guard test" in result.stdout


def test_test_cmd_baseline_output(monkeypatch) -> None:
    async def fake_run_agent_tests_with_baseline(skill, config):  # noqa: ARG001
        with_skill = AgentTestResult(
            skill_name="valid-skill",
            endpoint="https://mock-agent.test",
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            pass_rate=1.0,
            results=[],
            total_time_seconds=0.1,
            avg_latency_ms=12.0,
            passed=True,
        )
        baseline = AgentTestResult(
            skill_name="valid-skill",
            endpoint="https://mock-agent.test",
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            pass_rate=0.0,
            results=[],
            total_time_seconds=0.1,
            avg_latency_ms=30.0,
            passed=False,
        )
        return AgentTestComparisonResult(
            skill_name="valid-skill",
            endpoint="https://mock-agent.test",
            with_skill=with_skill,
            baseline=baseline,
            pass_rate_delta=1.0,
            passed_tests_delta=1,
            improved_tests=1,
            regressed_tests=0,
            unchanged_tests=0,
            comparisons=[
                EvalTestComparison(
                    test_name="basic",
                    with_skill_passed=True,
                    baseline_passed=False,
                    outcome="improved",
                    with_skill_latency_ms=12,
                    baseline_latency_ms=30,
                )
            ],
            passed=True,
        )

    monkeypatch.setattr(
        "skill_guard.commands.test.run_agent_tests_with_baseline",
        fake_run_agent_tests_with_baseline,
    )
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
            "--baseline",
        ],
    )
    assert result.exit_code == 0
    assert "pass_rate_delta" in result.stdout


def test_test_cmd_exits_five_on_hook_error(monkeypatch) -> None:
    async def fake_run_agent_tests(skill, config):  # noqa: ARG001
        raise HookError("pre-test hook failed")

    monkeypatch.setattr("skill_guard.commands.test.run_agent_tests", fake_run_agent_tests)
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
        ],
    )
    assert result.exit_code == 5
    assert "Test setup error" in result.stdout
    assert "injection_method=custom_hook" in result.stdout
    assert "Recommended CI path" in result.stdout


def test_test_cmd_exits_six_on_health_check_timeout(monkeypatch) -> None:
    async def fake_run_agent_tests(skill, config):  # noqa: ARG001
        raise HealthCheckTimeoutError("agent never became ready")

    monkeypatch.setattr("skill_guard.commands.test.run_agent_tests", fake_run_agent_tests)
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
        ],
    )
    assert result.exit_code == 6
    assert "Test setup error" in result.stdout
    assert "Health check failed" in result.stdout
    assert "reload_timeout_seconds" in result.stdout


def test_test_cmd_writes_workspace_artifact_on_setup_error(tmp_path: Path, monkeypatch) -> None:
    async def fake_run_agent_tests(skill, config):  # noqa: ARG001
        raise HookError("pre-test hook failed")

    monkeypatch.setattr("skill_guard.commands.test.run_agent_tests", fake_run_agent_tests)
    result = runner.invoke(
        app,
        [
            "test",
            str(FIXTURES / "valid-skill"),
            "--endpoint",
            "https://mock-agent.test",
            "--model",
            "gpt-4.1",
            "--workspace",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 5
    iteration_dir = tmp_path / "iteration-1"
    assert (iteration_dir / "setup_failure.json").is_file()
    assert (iteration_dir / "run.json").is_file()
