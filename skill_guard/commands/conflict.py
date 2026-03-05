"""CLI command: skill-gate conflict"""

from __future__ import annotations

from pathlib import Path

import typer

from skill_guard.config import load_config
from skill_guard.engine.similarity import compute_similarity
from skill_guard.models import ConfigError, SkillParseError
from skill_guard.output.json_out import format_as_json
from skill_guard.output.markdown import format_as_markdown
from skill_guard.output.text import format_conflict_result
from skill_guard.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
AGAINST_OPT = typer.Option(..., "--against", help="Skills dir or catalog YAML")
CONFIG_PATH_OPT = typer.Option(None, "--config", help="Path to skill-gate.yaml")
METHOD_OPT = typer.Option(None, "--method", help="tfidf|embeddings|llm")
THRESHOLD_OPT = typer.Option(None, "--threshold", help="Similarity threshold")
FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md")


def conflict_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    against: Path = AGAINST_OPT,
    config_path: Path | None = CONFIG_PATH_OPT,
    method: str | None = METHOD_OPT,
    threshold: float | None = THRESHOLD_OPT,
    format: str = FORMAT_OPT,
):
    """Detect trigger overlap with existing skills."""
    try:
        config = load_config(config_path)
        skill = parse_skill(skill_path)
        result = compute_similarity(
            skill, against, config.conflict, method=method, threshold=threshold
        )
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3) from e
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4) from e
    except NotImplementedError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1) from e

    if format == "json":
        typer.echo(format_as_json(result, command="conflict"))
    elif format in ("md", "markdown"):
        typer.echo(format_as_markdown(result, command="conflict"))
    else:
        format_conflict_result(result)

    if not result.passed:
        raise typer.Exit(code=1)
