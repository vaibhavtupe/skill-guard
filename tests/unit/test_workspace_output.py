from __future__ import annotations

import json
from pathlib import Path

from skill_guard.models import (
    AgentTestComparisonResult,
    AgentTestResult,
    EvalTestComparison,
    EvalTestResult,
)
from skill_guard.output.workspace import (
    write_workspace_comparison,
    write_workspace_results,
    write_workspace_setup_failure,
)


def _result(name: str, passed: bool) -> AgentTestResult:
    return AgentTestResult(
        skill_name="valid-skill",
        endpoint="https://mock-agent.test",
        total_tests=1,
        passed_tests=1 if passed else 0,
        failed_tests=0 if passed else 1,
        pass_rate=1.0 if passed else 0.0,
        results=[
            EvalTestResult(
                test_name=name,
                passed=passed,
                prompt="prompt",
                response_text="response",
                latency_ms=42,
                checks_passed=["contains:response"] if passed else [],
                checks_failed=[] if passed else ["contains:response"],
                skill_triggered=None,
                tool_calls=["tool"] if passed else [],
            )
        ],
        total_time_seconds=0.1,
        avg_latency_ms=42.0,
        passed=passed,
    )


def test_write_workspace_results(tmp_path: Path) -> None:
    iteration_dir = write_workspace_results(
        _result("basic test", True),
        tmp_path,
        injection_method="custom_hook",
        model="gpt-4.1",
        timeout_seconds=30,
        reload_command="./reload-agent.sh",
        reload_wait_seconds=5,
        reload_health_check_path="/health",
        reload_timeout_seconds=60,
    )
    outputs_dir = iteration_dir / "with_skill" / "basic_test" / "outputs"

    assert outputs_dir.is_dir()
    assert (outputs_dir / "response.txt").read_text(encoding="utf-8") == "response"
    assert json.loads((outputs_dir / "tool_calls.json").read_text(encoding="utf-8")) == ["tool"]
    timing = json.loads((outputs_dir / "timing.json").read_text(encoding="utf-8"))
    assert timing["latency_ms"] == 42
    grading = json.loads((outputs_dir / "grading.json").read_text(encoding="utf-8"))
    assert grading["passed"] is True
    assert (iteration_dir / "benchmark.json").is_file()
    run = json.loads((iteration_dir / "run.json").read_text(encoding="utf-8"))
    assert run["injection_method"] == "custom_hook"
    assert run["reload_command"] == "./reload-agent.sh"
    assert run["tests"] == ["basic test"]


def test_write_workspace_comparison(tmp_path: Path) -> None:
    with_skill = _result("basic", True)
    baseline = _result("basic", False)
    comparison = AgentTestComparisonResult(
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
                with_skill_latency_ms=42,
                baseline_latency_ms=50,
            )
        ],
        passed=True,
    )

    iteration_dir = write_workspace_comparison(
        comparison,
        tmp_path,
        injection_method="custom_hook",
        model="gpt-4.1",
        timeout_seconds=30,
        reload_command=None,
        reload_wait_seconds=0,
        reload_health_check_path="/health",
        reload_timeout_seconds=60,
    )

    assert (iteration_dir / "with_skill" / "basic" / "outputs" / "response.txt").is_file()
    assert (iteration_dir / "without_skill" / "basic" / "outputs" / "response.txt").is_file()
    assert (iteration_dir / "benchmark.json").is_file()
    run = json.loads((iteration_dir / "run.json").read_text(encoding="utf-8"))
    assert run["mode"] == "baseline_comparison"
    assert run["tests"] == ["basic"]


def test_write_workspace_setup_failure(tmp_path: Path) -> None:
    iteration_dir = write_workspace_setup_failure(
        tmp_path,
        skill_name="valid-skill",
        endpoint="https://mock-agent.test",
        mode="with_skill",
        injection_method="custom_hook",
        model="gpt-4.1",
        timeout_seconds=30,
        reload_command="./reload-agent.sh",
        reload_wait_seconds=5,
        reload_health_check_path="/health",
        reload_timeout_seconds=60,
        stage="setup",
        error_type="HookError",
        error_message="hook failed",
        remediation=["Verify the hook path."],
    )

    setup_failure = json.loads((iteration_dir / "setup_failure.json").read_text(encoding="utf-8"))
    assert setup_failure["stage"] == "setup"
    assert setup_failure["error_type"] == "HookError"
    assert setup_failure["remediation"] == ["Verify the hook path."]
