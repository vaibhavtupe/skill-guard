"""CLI command: skill-guard check."""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path
from typing import Any

import typer

from skill_guard.config import ConfigError, load_config
from skill_guard.engine.agent_runner import run_agent_tests
from skill_guard.engine.quality import run_validation
from skill_guard.engine.security import run_security_scan
from skill_guard.engine.similarity import compute_similarity
from skill_guard.models import HealthCheckTimeoutError, HookError, SkillParseError
from skill_guard.output.json_out import format_as_json
from skill_guard.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
AGAINST_OPT = typer.Option(..., "--against", help="Skills dir or catalog YAML")
ENDPOINT_OPT = typer.Option(None, "--endpoint", help="Agent endpoint URL")
CONFIG_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")
FORMAT_OPT = typer.Option(None, "--format", help="Output format: text|json|md")


def _emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json(payload, command="check"))
        return
    if output_format in ("md", "markdown"):
        typer.echo(
            "## skill-guard check\n\n"
            f"- skill: {payload['skill_name']}\n"
            f"- validation: {payload['validation']}\n"
            f"- security: {payload['security']}\n"
            f"- conflict: {payload['conflict']}\n"
            f"- test: {payload['test']}\n"
            f"- status: {payload['status']}\n"
            f"- summary: {payload['summary']}\n"
        )
        return

    typer.echo(
        f"skill={payload['skill_name']} validation={payload['validation']} "
        f"security={payload['security']} conflict={payload['conflict']} "
        f"test={payload['test']} status={payload['status']}\n{payload['summary']}"
    )


def check_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    against: Path = AGAINST_OPT,
    endpoint: str | None = ENDPOINT_OPT,
    config_path: Path | None = CONFIG_OPT,
    output_format: str | None = FORMAT_OPT,
) -> None:
    """Run validate + secure + conflict + test pipeline for a skill."""
    try:
        config = load_config(config_path)
        skill = parse_skill(skill_path)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3) from e
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4) from e

    resolved_output_format = output_format or config.ci.output_format
    if config.ci.post_pr_comment:
        warnings.warn(
            "ci.post_pr_comment is not yet implemented and has no effect.",
            stacklevel=2,
        )

    validation = run_validation(skill, config.validate)
    if validation.blockers > 0:
        _emit(
            {
                "skill_name": skill.metadata.name,
                "validation": "failed",
                "security": "skipped",
                "conflict": "skipped",
                "test": "skipped",
                "status": "failed",
                "summary": f"Validation failed with {validation.blockers} blocker(s).",
                "result": {
                    "validation": validation.model_dump(mode="json"),
                },
            },
            resolved_output_format,
        )
        raise typer.Exit(code=1)

    security = run_security_scan(skill, config.secure)
    if not security.passed:
        _emit(
            {
                "skill_name": skill.metadata.name,
                "validation": "passed" if validation.warnings == 0 else "warning",
                "security": "failed",
                "conflict": "skipped",
                "test": "skipped",
                "status": "failed",
                "summary": "Security scan failed.",
                "result": {
                    "validation": validation.model_dump(mode="json"),
                    "security": security.model_dump(mode="json"),
                },
            },
            resolved_output_format,
        )
        raise typer.Exit(code=1)
    try:
        conflict = compute_similarity(skill, against, config.conflict)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3) from e
    if not conflict.passed:
        _emit(
            {
                "skill_name": skill.metadata.name,
                "validation": "passed" if validation.warnings == 0 else "warning",
                "security": "passed",
                "conflict": "failed",
                "test": "skipped",
                "status": "failed",
                "summary": "Conflict detection found blocking overlap.",
                "result": {
                    "validation": validation.model_dump(mode="json"),
                    "security": security.model_dump(mode="json"),
                    "conflict": conflict.model_dump(mode="json"),
                },
            },
            resolved_output_format,
        )
        raise typer.Exit(code=1)

    resolved_endpoint = endpoint or config.test.endpoint
    validation_status = "passed" if validation.warnings == 0 else "warning"
    test_status = "skipped"
    test_result = None
    if resolved_endpoint:
        config.test.endpoint = resolved_endpoint
        try:
            test_result = asyncio.run(run_agent_tests(skill, config.test))
        except HealthCheckTimeoutError as e:
            typer.echo(f"Test setup error: {e}")
            raise typer.Exit(code=6) from e
        except HookError as e:
            typer.echo(f"Test setup error: {e}")
            raise typer.Exit(code=5) from e
        if test_result.passed:
            test_status = "passed"
        elif test_result.failed_tests > 0:
            _emit(
                {
                    "skill_name": skill.metadata.name,
                    "validation": validation_status,
                    "security": "passed",
                    "conflict": "passed",
                    "test": "failed",
                    "status": "failed",
                    "summary": "Agent evals failed with blocking failures.",
                    "result": {
                        "validation": validation.model_dump(mode="json"),
                        "security": security.model_dump(mode="json"),
                        "conflict": conflict.model_dump(mode="json"),
                        "test": test_result.model_dump(mode="json"),
                    },
                },
                resolved_output_format,
            )
            raise typer.Exit(code=1)
        else:
            test_status = "warning"

    has_warning = validation_status == "warning" or test_status == "warning"
    fail_on_warning = config.ci.fail_on_warning and has_warning
    final_status = "failed" if fail_on_warning else ("warning" if has_warning else "passed")
    _emit(
        {
            "skill_name": skill.metadata.name,
            "validation": validation_status,
            "security": "passed",
            "conflict": "passed",
            "test": test_status,
            "status": final_status,
            "summary": (
                "All blocking checks passed."
                if not has_warning
                else (
                    "Warnings are configured to fail this CI check."
                    if fail_on_warning
                    else "Blocking checks passed with warnings."
                )
            ),
            "result": {
                "validation": validation.model_dump(mode="json"),
                "security": security.model_dump(mode="json"),
                "conflict": conflict.model_dump(mode="json"),
                **(
                    {"test": test_result.model_dump(mode="json")} if test_result is not None else {}
                ),
            },
        },
        resolved_output_format,
    )

    if fail_on_warning:
        raise typer.Exit(code=1)
    if has_warning:
        raise typer.Exit(code=2)
