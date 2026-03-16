"""CLI command: skill-guard test."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer

from skill_guard.config import ConfigError, TestConfig, load_config
from skill_guard.engine.agent_runner import run_agent_tests
from skill_guard.models import HealthCheckTimeoutError, HookError, SkillParseError
from skill_guard.output.json_out import format_as_json
from skill_guard.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
ENDPOINT_OPT = typer.Option(None, "--endpoint", help="Agent endpoint URL")
API_KEY_OPT = typer.Option(None, "--api-key", help="Agent API key")
MODEL_OPT = typer.Option(None, "--model", help="Model name for /v1/responses")
CONFIG_PATH_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")
FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md")


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
        typer.echo(
            f"  - {status} {test_result['test_name']} "
            f"latency={test_result['latency_ms']}ms "
            f"tools={','.join(test_result['tool_calls']) if test_result['tool_calls'] else '-'}"
        )
        if test_result["checks_failed"]:
            typer.echo(f"    failed_checks={','.join(test_result['checks_failed'])}")


def test_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    endpoint: str | None = ENDPOINT_OPT,
    api_key: str | None = API_KEY_OPT,
    model: str | None = MODEL_OPT,
    config_path: Path | None = CONFIG_PATH_OPT,
    format: str = FORMAT_OPT,
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
        }
    )

    try:
        result = asyncio.run(run_agent_tests(skill, merged_test_config))
    except HealthCheckTimeoutError as e:
        typer.echo(f"Test setup error: {e}")
        raise typer.Exit(code=6) from e
    except HookError as e:
        typer.echo(f"Test setup error: {e}")
        raise typer.Exit(code=5) from e
    except OSError as e:
        typer.echo(f"Test execution error: {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Test execution error: {e}")
        raise typer.Exit(code=1) from e

    payload = result.model_dump(mode="json")
    _emit(payload, format)

    if result.pass_rate < 1.0:
        raise typer.Exit(code=1)
