"""CLI command: skill-guard suppress."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from ruamel.yaml import YAML

from skill_guard.engine.security import SECURITY_PATTERNS

SKILL_PATH_ARG = typer.Argument(..., help="Path to skill directory")
FINDING_OPT = typer.Option(..., "--finding", help="Finding ID to suppress (e.g. INJECT-002)")
REASON_OPT = typer.Option(None, "--reason", help="Reason for suppression (required)")

_VALID_IDS = {p.id for p in SECURITY_PATTERNS}


def suppress_cmd(
    skill_path: Path = SKILL_PATH_ARG,
    finding: str = FINDING_OPT,
    reason: str | None = REASON_OPT,
) -> None:
    """Suppress a false-positive finding with an auditable reason."""
    skill_path = skill_path.resolve()
    skill_md = skill_path / "SKILL.md"

    if not skill_md.is_file():
        typer.echo(f"Error: SKILL.md not found in '{skill_path}'")
        raise typer.Exit(code=4)

    finding = finding.upper()
    if finding not in _VALID_IDS:
        typer.echo(
            f"Error: unknown finding ID '{finding}'. Valid IDs: {', '.join(sorted(_VALID_IDS))}"
        )
        raise typer.Exit(code=3)

    # Require a reason — prompt interactively if TTY, otherwise error
    if not reason:
        if sys.stdin.isatty():
            reason = typer.prompt(f"Reason for suppressing {finding}")
            if not reason.strip():
                typer.echo("Error: Suppression reason cannot be empty.")
                raise typer.Exit(code=3)
        else:
            typer.echo(
                f"Error: Suppression requires a reason. Use --reason flag.\n"
                f'  skill-guard suppress {skill_path.name} --finding {finding} --reason "your reason"'
            )
            raise typer.Exit(code=3)

    # Add inline disable comment to SKILL.md
    _insert_disable_comment(skill_md, finding)

    # Append suppression record to skill-guard.yaml
    skill_name = skill_path.name
    _record_suppression(skill_path, finding, skill_name, reason)

    typer.echo(f"✓ Suppressed {finding} in {skill_name}")
    typer.echo(f"  Reason: {reason}")
    typer.echo("  Recorded in skill-guard.yaml under suppressions:")


def _insert_disable_comment(skill_md: Path, finding_id: str) -> None:
    """Insert a disable comment at the end of the SKILL.md frontmatter or body."""
    content = skill_md.read_text(encoding="utf-8")
    disable_line = f"<!-- skill-guard: disable={finding_id} -->\n"

    # If already suppressed, skip
    if f"disable={finding_id}" in content:
        return

    # Append before end of file
    if not content.endswith("\n"):
        content += "\n"
    content += disable_line
    skill_md.write_text(content, encoding="utf-8")


def _record_suppression(skill_path: Path, finding_id: str, skill_name: str, reason: str) -> None:
    """Append suppression record to skill-guard.yaml (or create it)."""
    # Walk up to find skill-guard.yaml, or create in skill_path parent
    config_path = _find_or_create_config(skill_path)

    yaml = YAML()
    yaml.preserve_quotes = True

    if config_path.exists():
        with open(config_path) as f:
            data = yaml.load(f) or {}
    else:
        data = {}

    if "suppressions" not in data:
        data["suppressions"] = []

    data["suppressions"].append(
        {
            "finding": finding_id,
            "skill": skill_name,
            "reason": reason,
            "suppressed_at": datetime.now(UTC).isoformat(),
        }
    )

    with open(config_path, "w") as f:
        yaml.dump(data, f)


def _find_or_create_config(skill_path: Path) -> Path:
    """Find skill-guard.yaml searching up from skill_path, or return a default location."""
    for parent in (skill_path, *skill_path.parents):
        for name in ("skill-guard.yaml", "skill-guard.yml"):
            candidate = parent / name
            if candidate.exists():
                return candidate
    # Default: create in skill parent directory
    return skill_path.parent / "skill-guard.yaml"
