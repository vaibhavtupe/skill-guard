"""CLI command: skill-guard init"""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from skill_guard.config import CONFIG_TEMPLATE

DEFAULT_DIR = Path.cwd()
DIR_OPT = typer.Option(DEFAULT_DIR, "--dir", help="Directory to initialize")
NO_CATALOG_OPT = typer.Option(
    True, "--no-catalog", help="Skip creating skill-catalog.yaml (Phase 1)"
)
TEMPLATE_OPT = typer.Option(None, "--template", help="Template name to scaffold")
OUTPUT_OPT = typer.Option(None, "--output", help="Output directory for the generated skill")
LIST_TEMPLATES_OPT = typer.Option(
    False, "--list-templates", help="List available templates and exit"
)
NAME_OPT = typer.Option(None, "--name", help="Override the generated skill name")
FORCE_OPT = typer.Option(False, "--force", help="Overwrite an existing non-empty output directory")

TEMPLATE_DESCRIPTIONS = {
    "base": "Minimal Anthropic-spec compliant skill scaffold",
    "weather-tool": "Skill for weather data retrieval via external API",
    "search-tool": "Skill for search and retrieval tasks",
}


def init_cmd(
    dir_path: Path = DIR_OPT,
    no_catalog: bool = NO_CATALOG_OPT,
    template: str | None = TEMPLATE_OPT,
    output: Path | None = OUTPUT_OPT,
    list_templates: bool = LIST_TEMPLATES_OPT,
    name: str | None = NAME_OPT,
    force: bool = FORCE_OPT,
):
    """Initialize skill-guard in a repository."""
    templates_dir = Path(__file__).resolve().parent.parent / "templates"
    if list_templates:
        typer.echo("Available templates:")
        for template_name in available_templates(templates_dir):
            typer.echo(f"  {template_name:<13} {TEMPLATE_DESCRIPTIONS[template_name]}")
        return

    if template is not None:
        scaffold_template(template, output, templates_dir, name=name, force=force)
        return

    _ = no_catalog  # reserved for Phase 2+ when catalog creation is supported
    dir_path = dir_path.resolve()
    dir_path.mkdir(parents=True, exist_ok=True)

    config_path = dir_path / "skill-guard.yaml"
    if not config_path.exists():
        config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
        typer.echo(f"Created {config_path}")
    else:
        typer.echo(f"Config already exists: {config_path}")

    # Create .github/workflows/skill-guard-ci.yml if .github exists
    github_dir = dir_path / ".github" / "workflows"
    if github_dir.exists():
        workflow_path = github_dir / "skill-guard-ci.yml"
        if not workflow_path.exists():
            workflow_path.write_text(_workflow_template(), encoding="utf-8")
            typer.echo(f"Created {workflow_path}")


def _workflow_template() -> str:
    return (
        """name: skill-guard CI\n\n"""
        + """
"""
        + """on:\n  pull_request:\n    branches: [main]\n\n"""
        + """
"""
        + """jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.11'\n      - run: pip install skill-guard\n      - run: skill-guard validate ./skills/example-skill\n"""
    )


def available_templates(templates_dir: Path) -> list[str]:
    return sorted(path.name for path in templates_dir.iterdir() if path.is_dir())


def scaffold_template(
    template: str,
    output: Path | None,
    templates_dir: Path,
    *,
    name: str | None,
    force: bool,
) -> None:
    template_dir = templates_dir / template
    if not template_dir.is_dir():
        typer.echo(f"Unknown template: {template}")
        raise typer.Exit(code=1)

    target_dir = (output or Path.cwd() / template).resolve()
    if target_dir.exists() and any(target_dir.iterdir()):
        if not force:
            typer.echo(f"Refusing to overwrite non-empty directory: {target_dir}")
            raise typer.Exit(code=1)
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    skill_name = name or target_dir.name
    for source in template_dir.rglob("*"):
        if source.is_dir():
            continue
        relative = source.relative_to(template_dir)
        target = target_dir / relative
        if target.suffix == ".tmpl":
            target = target.with_suffix("")
            rendered = source.read_text(encoding="utf-8").replace("__SKILL_NAME__", skill_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    display_path = (
        target_dir.relative_to(Path.cwd()) if target_dir.is_relative_to(Path.cwd()) else target_dir
    )
    typer.echo(f"Created {display_path}/ — run skill-guard validate {display_path}/ to verify")
