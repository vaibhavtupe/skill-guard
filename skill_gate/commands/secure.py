"""CLI command: skill-gate secure"""
from __future__ import annotations

from pathlib import Path

import typer

from skill_gate.config import load_config
from skill_gate.engine.security import run_security_scan
from skill_gate.models import ConfigError, SkillParseError
from skill_gate.output.json_out import format_as_json
from skill_gate.output.markdown import format_as_markdown
from skill_gate.output.text import format_security_result
from skill_gate.parser import parse_skill


def secure_cmd(
    skill_path: Path = typer.Argument(..., help="Path to skill directory"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to skill-gate.yaml"),
    format: str = typer.Option("text", "--format", help="Output format: text|json|md"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-essential output"),
):
    """Scan a skill for dangerous patterns."""
    try:
        config = load_config(config_path)
        skill = parse_skill(skill_path)
        result = run_security_scan(skill, config.secure)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3)
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4)

    if format == "json":
        typer.echo(format_as_json(result, command="secure"))
    elif format in ("md", "markdown"):
        typer.echo(format_as_markdown(result, command="secure"))
    else:
        format_security_result(result, quiet=quiet)

    if not result.passed:
        raise typer.Exit(code=1)
