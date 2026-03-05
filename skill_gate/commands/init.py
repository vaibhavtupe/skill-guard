"""CLI command: skill-gate init"""

from __future__ import annotations

from pathlib import Path

import typer

from skill_gate.config import CONFIG_TEMPLATE

DEFAULT_DIR = Path.cwd()
DIR_OPT = typer.Option(DEFAULT_DIR, "--dir", help="Directory to initialize")
NO_CATALOG_OPT = typer.Option(
    True, "--no-catalog", help="Skip creating skill-catalog.yaml (Phase 1)"
)


def init_cmd(
    dir_path: Path = DIR_OPT,
    no_catalog: bool = NO_CATALOG_OPT,
):
    """Initialize skill-gate in a repository."""
    _ = no_catalog  # reserved for Phase 2+ when catalog creation is supported
    dir_path = dir_path.resolve()
    dir_path.mkdir(parents=True, exist_ok=True)

    config_path = dir_path / "skill-gate.yaml"
    if not config_path.exists():
        config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
        typer.echo(f"Created {config_path}")
    else:
        typer.echo(f"Config already exists: {config_path}")

    # Create .github/workflows/skill-gate-ci.yml if .github exists
    github_dir = dir_path / ".github" / "workflows"
    if github_dir.exists():
        workflow_path = github_dir / "skill-gate-ci.yml"
        if not workflow_path.exists():
            workflow_path.write_text(_workflow_template(), encoding="utf-8")
            typer.echo(f"Created {workflow_path}")


def _workflow_template() -> str:
    return (
        """name: skill-gate CI\n\n"""
        + """
"""
        + """on:\n  pull_request:\n    branches: [main]\n\n"""
        + """
"""
        + """jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.11'\n      - run: pip install skill-gate\n      - run: skill-gate validate ./skills/example-skill\n"""
    )
