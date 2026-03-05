"""CLI command: skill-gate check."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from skill_gate.config import ConfigError, load_config
from skill_gate.engine.quality import run_validation
from skill_gate.engine.security import run_security_scan
from skill_gate.engine.similarity import compute_similarity
from skill_gate.models import SkillParseError
from skill_gate.output.json_out import format_as_json
from skill_gate.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
AGAINST_OPT = typer.Option(..., "--against", help="Skills dir or catalog YAML")
ENDPOINT_OPT = typer.Option(None, "--endpoint", help="Agent endpoint URL")
CONFIG_OPT = typer.Option(None, "--config", help="Path to skill-gate.yaml")
FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md")


def _emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json(payload, command="check"))
        return
    if output_format in ("md", "markdown"):
        typer.echo(
            "## skill-gate check\n\n"
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
    output_format: str = FORMAT_OPT,
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
            output_format,
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
            output_format,
        )
        raise typer.Exit(code=1)

    conflict = compute_similarity(skill, against, config.conflict)
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
            output_format,
        )
        raise typer.Exit(code=1)

    resolved_endpoint = endpoint or config.test.endpoint
    test_status = "skipped"
    warnings_only = validation.warnings > 0
    if resolved_endpoint:
        test_status = "warning"
        warnings_only = True

    final_status = "warning" if warnings_only else "passed"
    _emit(
        {
            "skill_name": skill.metadata.name,
            "validation": "passed" if validation.warnings == 0 else "warning",
            "security": "passed",
            "conflict": "passed",
            "test": test_status,
            "status": final_status,
            "summary": (
                "All blocking checks passed."
                if not warnings_only
                else "Blocking checks passed with warnings."
            ),
            "result": {
                "validation": validation.model_dump(mode="json"),
                "security": security.model_dump(mode="json"),
                "conflict": conflict.model_dump(mode="json"),
            },
        },
        output_format,
    )

    if warnings_only:
        raise typer.Exit(code=2)
