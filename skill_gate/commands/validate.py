"""CLI command: skill-gate validate"""
from __future__ import annotations

from pathlib import Path

import typer

from skill_gate.config import load_config
from skill_gate.engine.quality import run_validation
from skill_gate.models import ConfigError, SkillParseError
from skill_gate.output.json_out import format_as_json
from skill_gate.output.markdown import format_as_markdown
from skill_gate.output.text import format_validation_result
from skill_gate.parser import parse_skill


def validate_cmd(
    skill_path: Path = typer.Argument(..., help="Path to skill directory"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to skill-gate.yaml"),
    format: str = typer.Option("text", "--format", help="Output format: text|json|md"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-essential output"),
    verbose: bool = typer.Option(False, "--verbose", help="Show all check details"),
):
    """Validate a skill against format and quality rules."""
    try:
        config = load_config(config_path)
        skill = parse_skill(skill_path)
        result = run_validation(skill, config.validate)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3)
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4)

    if format == "json":
        typer.echo(format_as_json(result, command="validate"))
    elif format in ("md", "markdown"):
        typer.echo(format_as_markdown(result, command="validate"))
    else:
        format_validation_result(result, quiet=quiet, verbose=verbose)

    if result.blockers > 0:
        raise typer.Exit(code=1)
    if result.warnings > 0:
        raise typer.Exit(code=2)
