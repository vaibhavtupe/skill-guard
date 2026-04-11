"""CLI command: skill-guard test."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer

from skill_guard.config import ConfigError, TestConfig, load_config
from skill_guard.engine.agent_runner import (
    build_test_remediation,
    run_agent_tests,
    run_agent_tests_with_baseline,
)
from skill_guard.models import HealthCheckTimeoutError, HookError, SkillParseError
from skill_guard.output.json_out import format_as_json
from skill_guard.output.workspace import write_workspace_setup_failure
from skill_guard.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
ENDPOINT_OPT = typer.Option(None, "--endpoint", help="Agent endpoint URL")
API_KEY_OPT = typer.Option(None, "--api-key", help="Agent API key")
MODEL_OPT = typer.Option(None, "--model", help="Model name for /v1/responses")
CONFIG_PATH_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")
FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md")
WORKSPACE_OPT = typer.Option(
    None,
    "--workspace",
    help="Write AgentSkills-compatible eval artifacts to this directory",
)
BASELINE_OPT = typer.Option(
    False,
    "--baseline",
    help="Run baseline evals without skill injection for comparison",
)


def _emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json(payload, command="test"))
        return

    if output_format in ("md", "markdown"):
        lines = [
            "## skill-guard test",
            "",
            f"- skill: {payload['skill_name']}",
            f"- endpoint: {payload['endpoint']}",
            f"- passed: {payload['passed_tests']}/{payload['total_tests']}",
            f"- pass_rate: {payload['pass_rate']:.2%}",
            f"- avg_latency_ms: {payload['avg_latency_ms']:.1f}",
            f"- status: {'passed' if payload['passed'] else 'failed'}",
        ]
        typer.echo("\n".join(lines))
        return

    typer.echo(
        f"skill={payload['skill_name']} endpoint={payload['endpoint']} "
        f"passed={payload['passed_tests']}/{payload['total_tests']} "
        f"pass_rate={payload['pass_rate']:.2%} avg_latency_ms={payload['avg_latency_ms']:.1f} "
        f"status={'passed' if payload['passed'] else 'failed'}"
    )
    for test_result in payload["results"]:
        status = "PASS" if test_result["passed"] else "FAIL"
        review_suffix = " (review)" if test_result.get("needs_review") else ""
        typer.echo(
            f"  - {status}{review_suffix} {test_result['test_name']} "
            f"latency={test_result['latency_ms']}ms "
            f"tools={','.join(test_result['tool_calls']) if test_result['tool_calls'] else '-'}"
        )
        if test_result.get("needs_review") and test_result.get("expected_output"):
            typer.echo(f"    expected_output={test_result['expected_output']}")
        if test_result["checks_failed"]:
            typer.echo(f"    failed_checks={','.join(test_result['checks_failed'])}")


def _emit_baseline(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json(payload, command="test"))
        return

    if output_format in ("md", "markdown"):
        lines = [
            "## skill-guard test (baseline)",
            "",
            f"- skill: {payload['skill_name']}",
            f"- endpoint: {payload['endpoint']}",
            f"- with_skill: {payload['with_skill']['passed_tests']}/{payload['with_skill']['total_tests']}",
            f"- baseline: {payload['baseline']['passed_tests']}/{payload['baseline']['total_tests']}",
            f"- pass_rate_delta: {payload['pass_rate_delta']:.2%}",
            f"- improved/regressed/unchanged: {payload['improved_tests']}/{payload['regressed_tests']}/{payload['unchanged_tests']}",
            f"- status: {'passed' if payload['passed'] else 'failed'}",
        ]
        typer.echo("\n".join(lines))
        return

    typer.echo(
        f"skill={payload['skill_name']} endpoint={payload['endpoint']} "
        f"with_skill={payload['with_skill']['passed_tests']}/{payload['with_skill']['total_tests']} "
        f"baseline={payload['baseline']['passed_tests']}/{payload['baseline']['total_tests']} "
        f"pass_rate_delta={payload['pass_rate_delta']:.2%} "
        f"status={'passed' if payload['passed'] else 'failed'}"
    )
    for comparison in payload["comparisons"]:
        with_status = "PASS" if comparison["with_skill_passed"] else "FAIL"
        baseline_status = "PASS" if comparison["baseline_passed"] else "FAIL"
        typer.echo(
            f"  - {comparison['test_name']} with={with_status} baseline={baseline_status} "
            f"outcome={comparison['outcome']}"
        )


def test_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    endpoint: str | None = ENDPOINT_OPT,
    api_key: str | None = API_KEY_OPT,
    model: str | None = MODEL_OPT,
    config_path: Path | None = CONFIG_PATH_OPT,
    format: str = FORMAT_OPT,
    workspace: str | None = WORKSPACE_OPT,
    baseline: bool = BASELINE_OPT,
) -> None:
    """Run evals against an agent endpoint via the OpenAI Responses API."""
    try:
        config = load_config(config_path)
        skill = parse_skill(skill_path)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3) from e
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4) from e

    merged_test_config = TestConfig.model_validate(
        {
            **config.test.model_dump(),
            "endpoint": endpoint if endpoint is not None else config.test.endpoint,
            "api_key": api_key if api_key is not None else config.test.api_key,
            "model": model if model is not None else config.test.model,
            "workspace_dir": workspace if workspace is not None else config.test.workspace_dir,
        }
    )

    run_baseline = baseline or getattr(config.test, "baseline", False)
    test_mode = "baseline_comparison" if run_baseline else "with_skill"

    try:
        if run_baseline:
            result = asyncio.run(run_agent_tests_with_baseline(skill, merged_test_config))
        else:
            result = asyncio.run(run_agent_tests(skill, merged_test_config))
    except HealthCheckTimeoutError as e:
        _write_setup_failure_artifact(
            skill_name=skill.metadata.name,
            test_mode=test_mode,
            test_config=merged_test_config,
            error=e,
        )
        typer.echo(_format_setup_error("Health check failed", e, merged_test_config))
        raise typer.Exit(code=6) from e
    except HookError as e:
        _write_setup_failure_artifact(
            skill_name=skill.metadata.name,
            test_mode=test_mode,
            test_config=merged_test_config,
            error=e,
        )
        typer.echo(_format_setup_error("Injection/setup failed", e, merged_test_config))
        raise typer.Exit(code=5) from e
    except OSError as e:
        typer.echo(f"Test execution error: {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Test execution error: {e}")
        raise typer.Exit(code=1) from e

    payload = result.model_dump(mode="json")
    if run_baseline:
        _emit_baseline(payload, format)
    else:
        _emit(payload, format)

    if run_baseline:
        if result.with_skill.pass_rate < 1.0:
            raise typer.Exit(code=1)
    else:
        if result.pass_rate < 1.0:
            raise typer.Exit(code=1)


def _write_setup_failure_artifact(
    *,
    skill_name: str,
    test_mode: str,
    test_config: TestConfig,
    error: Exception,
) -> None:
    if not test_config.workspace_dir:
        return

    write_workspace_setup_failure(
        Path(test_config.workspace_dir),
        skill_name=skill_name,
        endpoint=test_config.endpoint,
        mode=test_mode,
        injection_method=test_config.injection.method,
        model=test_config.model,
        timeout_seconds=test_config.timeout_seconds,
        reload_command=test_config.reload_command,
        reload_wait_seconds=test_config.reload_wait_seconds,
        reload_health_check_path=test_config.reload_health_check_path,
        reload_timeout_seconds=test_config.reload_timeout_seconds,
        stage="setup",
        error_type=type(error).__name__,
        error_message=str(error),
        remediation=build_test_remediation(test_config, error),
    )


def _format_setup_error(prefix: str, error: Exception, test_config: TestConfig) -> str:
    remediation = build_test_remediation(test_config, error)
    lines = [
        f"Test setup error: {prefix}: {error}",
        f"  injection_method={test_config.injection.method}",
    ]
    if test_config.reload_command:
        lines.append(f"  reload_command={test_config.reload_command}")
    lines.extend(f"  remediation: {step}" for step in remediation)
    if test_config.workspace_dir:
        lines.append(
            f"  workspace_artifact={Path(test_config.workspace_dir)} "
            "(see latest iteration setup_failure.json)"
        )
    return "\n".join(lines)
