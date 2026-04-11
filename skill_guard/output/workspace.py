"""Workspace output artifacts for eval runs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from skill_guard.models import AgentTestComparisonResult, AgentTestResult, EvalTestResult

_ITERATION_PATTERN = re.compile(r"^iteration-(\d+)$")


def _next_iteration_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    existing = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = _ITERATION_PATTERN.match(child.name)
        if match:
            existing.append(int(match.group(1)))
    next_index = max(existing, default=0) + 1
    iteration_dir = root / f"iteration-{next_index}"
    iteration_dir.mkdir(parents=True, exist_ok=False)
    return iteration_dir


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")
    return slug or "test"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_test_outputs(test_dir: Path, result: EvalTestResult) -> None:
    outputs_dir = test_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    (outputs_dir / "response.txt").write_text(result.response_text, encoding="utf-8")
    _write_json(outputs_dir / "tool_calls.json", result.tool_calls)
    _write_json(
        outputs_dir / "timing.json",
        {
            "latency_ms": result.latency_ms,
        },
    )
    _write_json(
        outputs_dir / "grading.json",
        {
            "passed": result.passed,
            "checks_passed": result.checks_passed,
            "checks_failed": result.checks_failed,
            "needs_review": result.needs_review,
            "expected_output": result.expected_output,
        },
    )


def _write_run(iteration_dir: Path, label: str, result: AgentTestResult) -> None:
    run_dir = iteration_dir / label
    run_dir.mkdir(parents=True, exist_ok=True)

    for test in result.results:
        test_dir = run_dir / _slugify(test.test_name)
        _write_test_outputs(test_dir, test)


def _benchmark_payload(result: AgentTestResult) -> dict[str, Any]:
    return {
        "skill_name": result.skill_name,
        "endpoint": result.endpoint,
        "total_tests": result.total_tests,
        "passed_tests": result.passed_tests,
        "failed_tests": result.failed_tests,
        "pass_rate": result.pass_rate,
        "avg_latency_ms": result.avg_latency_ms,
        "total_time_seconds": result.total_time_seconds,
        "passed": result.passed,
    }


def _run_metadata_payload(
    result: AgentTestResult,
    *,
    mode: str,
    injection_method: str,
    model: str | None,
    timeout_seconds: int,
    reload_command: str | None,
    reload_wait_seconds: int,
    reload_health_check_path: str,
    reload_timeout_seconds: int,
) -> dict[str, Any]:
    return {
        "skill_name": result.skill_name,
        "endpoint": result.endpoint,
        "mode": mode,
        "injection_method": injection_method,
        "model": model,
        "timeout_seconds": timeout_seconds,
        "reload_command": reload_command,
        "reload_wait_seconds": reload_wait_seconds,
        "reload_health_check_path": reload_health_check_path,
        "reload_timeout_seconds": reload_timeout_seconds,
        "tests": [test.test_name for test in result.results],
    }


def write_workspace_results(
    result: AgentTestResult,
    workspace_root: Path,
    *,
    injection_method: str,
    model: str | None,
    timeout_seconds: int,
    reload_command: str | None,
    reload_wait_seconds: int,
    reload_health_check_path: str,
    reload_timeout_seconds: int,
) -> Path:
    iteration_dir = _next_iteration_dir(workspace_root)
    _write_run(iteration_dir, "with_skill", result)
    _write_json(iteration_dir / "benchmark.json", _benchmark_payload(result))
    _write_json(
        iteration_dir / "run.json",
        _run_metadata_payload(
            result,
            mode="with_skill",
            injection_method=injection_method,
            model=model,
            timeout_seconds=timeout_seconds,
            reload_command=reload_command,
            reload_wait_seconds=reload_wait_seconds,
            reload_health_check_path=reload_health_check_path,
            reload_timeout_seconds=reload_timeout_seconds,
        ),
    )
    return iteration_dir


def write_workspace_comparison(
    result: AgentTestComparisonResult,
    workspace_root: Path,
    *,
    injection_method: str,
    model: str | None,
    timeout_seconds: int,
    reload_command: str | None,
    reload_wait_seconds: int,
    reload_health_check_path: str,
    reload_timeout_seconds: int,
) -> Path:
    iteration_dir = _next_iteration_dir(workspace_root)
    _write_run(iteration_dir, "with_skill", result.with_skill)
    _write_run(iteration_dir, "without_skill", result.baseline)
    _write_json(
        iteration_dir / "benchmark.json",
        {
            "skill_name": result.skill_name,
            "endpoint": result.endpoint,
            "with_skill": _benchmark_payload(result.with_skill),
            "without_skill": _benchmark_payload(result.baseline),
            "pass_rate_delta": result.pass_rate_delta,
            "passed_tests_delta": result.passed_tests_delta,
            "improved_tests": result.improved_tests,
            "regressed_tests": result.regressed_tests,
            "unchanged_tests": result.unchanged_tests,
            "passed": result.passed,
        },
    )
    _write_json(
        iteration_dir / "run.json",
        {
            "skill_name": result.skill_name,
            "endpoint": result.endpoint,
            "mode": "baseline_comparison",
            "injection_method": injection_method,
            "model": model,
            "timeout_seconds": timeout_seconds,
            "reload_command": reload_command,
            "reload_wait_seconds": reload_wait_seconds,
            "reload_health_check_path": reload_health_check_path,
            "reload_timeout_seconds": reload_timeout_seconds,
            "tests": [test.test_name for test in result.with_skill.results],
        },
    )
    return iteration_dir


def write_workspace_setup_failure(
    workspace_root: Path,
    *,
    skill_name: str,
    endpoint: str | None,
    mode: str,
    injection_method: str,
    model: str | None,
    timeout_seconds: int,
    reload_command: str | None,
    reload_wait_seconds: int,
    reload_health_check_path: str,
    reload_timeout_seconds: int,
    stage: str,
    error_type: str,
    error_message: str,
    remediation: list[str],
) -> Path:
    iteration_dir = _next_iteration_dir(workspace_root)
    _write_json(
        iteration_dir / "run.json",
        {
            "skill_name": skill_name,
            "endpoint": endpoint,
            "mode": mode,
            "injection_method": injection_method,
            "model": model,
            "timeout_seconds": timeout_seconds,
            "reload_command": reload_command,
            "reload_wait_seconds": reload_wait_seconds,
            "reload_health_check_path": reload_health_check_path,
            "reload_timeout_seconds": reload_timeout_seconds,
            "tests": [],
        },
    )
    _write_json(
        iteration_dir / "setup_failure.json",
        {
            "stage": stage,
            "error_type": error_type,
            "error_message": error_message,
            "remediation": remediation,
        },
    )
    return iteration_dir
