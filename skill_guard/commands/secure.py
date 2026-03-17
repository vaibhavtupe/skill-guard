"""CLI command: skill-guard secure"""

from __future__ import annotations

from pathlib import Path

import typer

from skill_guard.config import load_config
from skill_guard.engine.security import run_security_scan
from skill_guard.models import ConfigError, SkillParseError
from skill_guard.output.json_out import format_as_json
from skill_guard.output.markdown import format_as_markdown
from skill_guard.output.text import format_security_result
from skill_guard.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
CONFIG_PATH_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")
FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md")
QUIET_OPT = typer.Option(False, "--quiet", help="Suppress non-essential output")
SKIP_REFERENCES_OPT = typer.Option(
    False,
    "--skip-references",
    help="Skip scanning references/ files for injection patterns",
)


def secure_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    config_path: Path | None = CONFIG_PATH_OPT,
    format: str = FORMAT_OPT,
    quiet: bool = QUIET_OPT,
    skip_references: bool = SKIP_REFERENCES_OPT,
):
    """Scan a skill for dangerous patterns."""
    try:
        config = load_config(config_path)
        if skip_references:
            config.secure.skip_references = True
        skill = parse_skill(skill_path)
        result = run_security_scan(skill, config.secure)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3) from e
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4) from e

    if format == "json":
        typer.echo(format_as_json(result, command="secure"))
    elif format in ("md", "markdown"):
        typer.echo(format_as_markdown(result, command="secure"))
    else:
        format_security_result(result, quiet=quiet)

    if not result.passed:
        raise typer.Exit(code=1)
