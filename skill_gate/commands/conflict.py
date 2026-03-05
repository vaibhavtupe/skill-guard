"""CLI command: skill-gate conflict"""
from __future__ import annotations

from pathlib import Path

import typer

from skill_gate.config import load_config
from skill_gate.engine.similarity import compute_similarity
from skill_gate.models import ConfigError, SkillParseError
from skill_gate.output.json_out import format_as_json
from skill_gate.output.markdown import format_as_markdown
from skill_gate.output.text import format_conflict_result
from skill_gate.parser import parse_skill


def conflict_cmd(
    skill_path: Path = typer.Argument(..., help="Path to skill directory"),
    against: Path = typer.Option(..., "--against", help="Skills dir or catalog YAML"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to skill-gate.yaml"),
    method: str | None = typer.Option(None, "--method", help="tfidf|embeddings|llm"),
    threshold: float | None = typer.Option(None, "--threshold", help="Similarity threshold"),
    format: str = typer.Option("text", "--format", help="Output format: text|json|md"),
):
    """Detect trigger overlap with existing skills."""
    try:
        config = load_config(config_path)
        skill = parse_skill(skill_path)
        result = compute_similarity(skill, against, config.conflict, method=method, threshold=threshold)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3)
    except SkillParseError as e:
        typer.echo(f"Parse error: {e}")
        raise typer.Exit(code=4)
    except NotImplementedError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)

    if format == "json":
        typer.echo(format_as_json(result, command="conflict"))
    elif format in ("md", "markdown"):
        typer.echo(format_as_markdown(result, command="conflict"))
    else:
        format_conflict_result(result)

    if not result.passed:
        raise typer.Exit(code=1)
