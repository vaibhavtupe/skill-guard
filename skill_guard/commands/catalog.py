"""CLI subcommands for skill catalog management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from skill_guard.config import load_config
from skill_guard.engine.catalog_manager import CatalogManager
from skill_guard.engine.quality import run_validation
from skill_guard.output.json_out import format_as_json
from skill_guard.parser import parse_skill

catalog_app = typer.Typer(name="catalog", help="Manage the skill catalog.")
_manager = CatalogManager()

FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md")
STAGE_OPT = typer.Option(None, "--stage", help="Filter by stage")
AUTHOR_OPT = typer.Option(None, "--author", help="Filter by author")
TAG_OPT = typer.Option(None, "--tag", help="Filter by tag")
CATALOG_OPT = typer.Option(None, "--catalog", help="Catalog YAML path")
SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
QUERY_ARG = typer.Argument(..., help="Search query")
CONFIG_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")


def _resolve_catalog_path(catalog_path: Path | None, config_path: Path | None = None) -> Path:
    if catalog_path is not None:
        return catalog_path
    config = load_config(config_path)
    return Path(config.catalog_path)


def _entry_to_dict(entry: Any) -> dict[str, Any]:
    if hasattr(entry, "model_dump"):
        return entry.model_dump(mode="json")
    return dict(entry)


def _render_entries(entries: list[Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json([_entry_to_dict(e) for e in entries], command="catalog list"))
        return

    if output_format in ("md", "markdown"):
        rows = [
            f"| {e.name} | {e.stage} | {e.author} | {e.version} | {e.quality_score} |"
            for e in entries
        ]
        if not rows:
            rows = ["| - | - | - | - | - |"]
        typer.echo(
            "## skill-guard catalog list\n\n"
            "| Name | Stage | Author | Version | Score |\n"
            "|---|---|---|---|---|\n" + "\n".join(rows)
        )
        return

    if not entries:
        typer.echo("No catalog entries found.")
        return
    for entry in entries:
        typer.echo(
            f"{entry.name} [{entry.stage}] v{entry.version} by {entry.author} "
            f"(score={entry.quality_score})"
        )


@catalog_app.command("list")
def list_cmd(
    stage: str | None = STAGE_OPT,
    author: str | None = AUTHOR_OPT,
    tag: str | None = TAG_OPT,
    catalog_path: Path | None = CATALOG_OPT,
    output_format: str = FORMAT_OPT,
) -> None:
    catalog = _manager.load_catalog(_resolve_catalog_path(catalog_path))
    entries = _manager.list_skills(catalog, stage=stage, author=author, tag=tag)
    _render_entries(entries, output_format)


@catalog_app.command("register")
def register_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    catalog_path: Path | None = CATALOG_OPT,
    config_path: Path | None = CONFIG_OPT,
) -> None:
    config = load_config(config_path)
    catalog_file = _resolve_catalog_path(catalog_path, config_path=config_path)
    skill = parse_skill(skill_path)
    validation = run_validation(skill, config.validate)
    entry = _manager.register_skill(skill, validation, catalog_file)
    typer.echo(
        f"Registered {entry.name} [{entry.stage}] in {catalog_file} (score={entry.quality_score})"
    )


@catalog_app.command("search")
def search_cmd(
    query: str = QUERY_ARG,
    catalog_path: Path | None = CATALOG_OPT,
    output_format: str = FORMAT_OPT,
) -> None:
    catalog = _manager.load_catalog(_resolve_catalog_path(catalog_path))
    entries = _manager.search_skills(catalog, query)
    _render_entries(entries, output_format)


@catalog_app.command("stats")
def stats_cmd(
    catalog_path: Path | None = CATALOG_OPT,
    output_format: str = FORMAT_OPT,
) -> None:
    catalog = _manager.load_catalog(_resolve_catalog_path(catalog_path))
    stats = _manager.get_stats(catalog)

    if output_format == "json":
        typer.echo(format_as_json(stats, command="catalog stats"))
    elif output_format in ("md", "markdown"):
        typer.echo(
            "## skill-guard catalog stats\n\n"
            f"- total: {stats['total']}\n"
            f"- staging: {stats['staging']}\n"
            f"- production: {stats['production']}\n"
            f"- degraded: {stats['degraded']}\n"
            f"- deprecated: {stats['deprecated']}\n"
        )
    else:
        typer.echo(
            f"total={stats['total']} staging={stats['staging']} production={stats['production']} "
            f"degraded={stats['degraded']} deprecated={stats['deprecated']}"
        )
