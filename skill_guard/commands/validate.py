"""CLI command: skill-guard validate"""

from __future__ import annotations

from pathlib import Path

import typer
from ruamel.yaml import YAML

from skill_guard.config import load_config
from skill_guard.engine.quality import run_validation
from skill_guard.models import ConfigError, SkillParseError
from skill_guard.output.json_out import format_as_json
from skill_guard.output.markdown import format_as_markdown
from skill_guard.output.text import format_validation_result
from skill_guard.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
CONFIG_PATH_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")
FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md")
QUIET_OPT = typer.Option(False, "--quiet", help="Suppress non-essential output")
VERBOSE_OPT = typer.Option(False, "--verbose", help="Show all check details")
SHOW_SUPPRESSED_OPT = typer.Option(
    False, "--show-suppressed", help="List all suppression records for this skill"
)


def validate_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    config_path: Path | None = CONFIG_PATH_OPT,
    format: str = FORMAT_OPT,
    quiet: bool = QUIET_OPT,
    verbose: bool = VERBOSE_OPT,
    show_suppressed: bool = SHOW_SUPPRESSED_OPT,
):
    """Validate a skill against format and quality rules."""
    try:
        config = load_config(config_path)
        skill = parse_skill(skill_path)
        result = run_validation(skill, config.validate)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3) from e
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4) from e

    if format == "json":
        typer.echo(format_as_json(result, command="validate"))
    elif format in ("md", "markdown"):
        typer.echo(format_as_markdown(result, command="validate"))
    else:
        format_validation_result(result, quiet=quiet, verbose=verbose)

    # Show suppression records if requested
    if show_suppressed:
        _show_suppression_records(skill_path.resolve())

    if result.blockers > 0:
        raise typer.Exit(code=1)
    if result.warnings > 0:
        raise typer.Exit(code=2)


def _show_suppression_records(skill_path: Path) -> None:
    """Print suppression records for this skill from skill-guard.yaml."""
    skill_name = skill_path.name
    # Search for skill-guard.yaml walking up
    config_file: Path | None = None
    for parent in (skill_path, *skill_path.parents):
        for name in ("skill-guard.yaml", "skill-guard.yml"):
            candidate = parent / name
            if candidate.exists():
                config_file = candidate
                break
        if config_file:
            break

    if not config_file:
        typer.echo("\nNo suppressions found (no skill-guard.yaml located).")
        return

    yaml = YAML()
    with open(config_file) as f:
        data = yaml.load(f) or {}

    suppressions = [s for s in data.get("suppressions", []) if s.get("skill") == skill_name]
    if not suppressions:
        typer.echo(f"\nNo suppressions recorded for '{skill_name}'.")
        return

    typer.echo(f"\nSuppressions for '{skill_name}' ({len(suppressions)}):")
    for s in suppressions:
        typer.echo(
            f"  ⊘ {s['finding']} — {s['reason']} (suppressed {s.get('suppressed_at', 'unknown')})"
        )
