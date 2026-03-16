"""Helpers for pre-commit integration."""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

import typer

from skill_guard.config import ConfigError, load_config
from skill_guard.engine.quality import run_validation
from skill_guard.engine.security import run_security_scan
from skill_guard.engine.similarity import compute_similarity
from skill_guard.models import SkillParseError
from skill_guard.parser import parse_skill

VALID_COMMANDS = {"validate", "secure", "check"}


def find_skill_root(path: Path) -> Path | None:
    """Walk up from a changed path until a skill root is found."""
    candidate = path.resolve()
    if candidate.is_file():
        candidate = candidate.parent

    for current in (candidate, *candidate.parents):
        if (current / "SKILL.md").is_file():
            return current
    return None


def collect_skill_roots(paths: Sequence[Path]) -> list[Path]:
    """Resolve changed file paths to unique skill roots."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        root = find_skill_root(path)
        if root is None or root in seen:
            continue
        seen.add(root)
        roots.append(root)
    return roots


def _run_command(command: str, skill_root: Path) -> int:
    try:
        config = load_config()
        skill = parse_skill(skill_root)
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}")
        return 3
    except SkillParseError as exc:
        typer.echo(f"Parse error: {exc}")
        return 4

    if command == "validate":
        result = run_validation(skill, config.validate)
        return 1 if result.blockers > 0 else (2 if result.warnings > 0 else 0)
    if command == "secure":
        result = run_security_scan(skill, config.secure)
        return 0 if result.passed else 1

    validation = run_validation(skill, config.validate)
    if validation.blockers > 0:
        return 1
    security = run_security_scan(skill, config.secure)
    if not security.passed:
        return 1
    conflict = compute_similarity(skill, skill_root.parent, config.conflict)
    if not conflict.passed:
        return 1
    return 2 if validation.warnings > 0 else 0


def pre_commit_run(command: str, files: Sequence[str | Path]) -> int:
    """Run a skill-guard command for the changed skills in a pre-commit hook."""
    if command not in VALID_COMMANDS:
        typer.echo(f"Unsupported pre-commit command: {command}")
        return 3

    roots = collect_skill_roots([Path(file) for file in files])
    if not roots:
        typer.echo("No skill changes detected.")
        return 0

    exit_code = 0
    for root in roots:
        exit_code = max(exit_code, _run_command(command, root))
    return exit_code


def main(files: Iterable[str] | None = None) -> None:
    """Entry point for the pre-commit hook wrapper."""
    args = list(files) if files is not None else sys.argv[1:]
    if not args:
        raise typer.Exit(code=3)

    command, *changed_files = args
    raise typer.Exit(code=pre_commit_run(command, changed_files))
