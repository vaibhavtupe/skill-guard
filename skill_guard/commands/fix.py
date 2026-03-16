"""CLI command: skill-guard fix."""

from __future__ import annotations

from pathlib import Path

import typer

from skill_guard.engine.fixer import apply_fixes, plan_fixes
from skill_guard.models import SkillParseError
from skill_guard.parser import parse_skill

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
CHECK_OPT = typer.Option(False, "--check", help="Dry run; report fixes without writing files")


def fix_cmd(skill_path: Path = SKILL_PATH_ARG, check: bool = CHECK_OPT) -> None:
    """Repair deterministic validation issues in SKILL.md."""
    skill_path = skill_path.resolve()
    skill_md_path = skill_path / "SKILL.md"
    if not skill_md_path.is_file():
        typer.echo(f"Parse error: SKILL.md not found in '{skill_path}'")
        raise typer.Exit(code=4)

    try:
        parsed_skill = parse_skill(skill_path)
    except SkillParseError:
        parsed_skill = None

    fix_plans = plan_fixes(parsed_skill, skill_path)
    available_fixes = sum(1 for plan in fix_plans if plan.reason_if_not is None)
    manual_fixes = sum(1 for plan in fix_plans if plan.reason_if_not is not None)

    if check:
        typer.echo(f"0 fixes applied, {manual_fixes} manual fixes required")
        for plan in fix_plans:
            if plan.reason_if_not is not None:
                typer.echo(plan.reason_if_not)
            else:
                typer.echo(f"Available fix: {plan.description}")
        if available_fixes > 0:
            raise typer.Exit(code=1)
        return

    applied = apply_fixes(skill_path, fix_plans)
    typer.echo(f"{applied} fixes applied, {manual_fixes} manual fixes required")
    for plan in fix_plans:
        if plan.reason_if_not is not None:
            typer.echo(plan.reason_if_not)
