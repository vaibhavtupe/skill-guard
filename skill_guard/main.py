"""skill-guard CLI entrypoint."""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import typer

from skill_guard.commands import conflict, fix, init, secure, test, validate
from skill_guard.commands.catalog import catalog_app
from skill_guard.commands.check import check_cmd
from skill_guard.commands.monitor import monitor_cmd
from skill_guard.commands.suppress import suppress_cmd

app = typer.Typer(
    name="skill-guard",
    help=(
        "The quality gate for Agent Skills.\n\n"
        "Start with `skill-guard check <skill-or-skills-root>` for the default pre-merge workflow."
    ),
    no_args_is_help=True,
)
_VERSION_CHECK_CACHE_PATH = Path.home() / ".cache" / "skill-guard" / "version-check"
_VERSION_CHECK_TTL_SECONDS = 24 * 60 * 60


def _version_callback(value: bool) -> None:
    if value:
        v = importlib.metadata.version("skill-guard")
        typer.echo(v)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: FBT001
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Start with `skill-guard check` for the default workflow."""
    _start_version_check()


def _start_version_check() -> None:
    if os.environ.get("SKILL_GUARD_NO_UPDATE_CHECK") == "1":
        return

    cached_latest = _read_cached_latest_version()
    if cached_latest is not None:
        _print_update_notice_if_needed(cached_latest)
        return

    thread = threading.Thread(target=_refresh_version_cache, daemon=True)
    thread.start()


def _read_cached_latest_version() -> str | None:
    if not _VERSION_CHECK_CACHE_PATH.exists():
        return None

    try:
        if time.time() - _VERSION_CHECK_CACHE_PATH.stat().st_mtime >= _VERSION_CHECK_TTL_SECONDS:
            return None
        payload = json.loads(_VERSION_CHECK_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

    latest = payload.get("latest")
    return latest if isinstance(latest, str) and latest else None


def _refresh_version_cache() -> None:
    try:
        with urlopen("https://pypi.org/pypi/skill-guard/json", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        latest = payload.get("info", {}).get("version")
        if not isinstance(latest, str) or not latest:
            return

        _VERSION_CHECK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _VERSION_CHECK_CACHE_PATH.write_text(
            json.dumps({"latest": latest, "checked_at": int(time.time())}),
            encoding="utf-8",
        )
        _print_update_notice_if_needed(latest)
    except Exception:
        return


def _print_update_notice_if_needed(latest: str) -> None:
    try:
        current = importlib.metadata.version("skill-guard")
    except importlib.metadata.PackageNotFoundError:
        return

    if _version_tuple(latest) > _version_tuple(current):
        print(
            f"ℹ️  skill-guard {latest} available — upgrade: pip install --upgrade skill-guard",
            file=sys.stderr,
            flush=True,
        )


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


# Register subcommands
app.command(
    "check",
    help="Default gate: run validate + secure + conflict, and test if --endpoint is set.",
    rich_help_panel="Primary Workflow",
)(check_cmd)
app.command(
    "init",
    help="Initialize a repo or scaffold a skill so you can start using `check` quickly.",
    rich_help_panel="Primary Workflow",
)(init.init_cmd)
app.command(
    "validate",
    help="Inspect one part of the gate in isolation: format and metadata quality checks.",
    rich_help_panel="Core Building Blocks",
)(validate.validate_cmd)
app.command(
    "secure",
    help="Inspect one part of the gate in isolation: security and injection pattern checks.",
    rich_help_panel="Core Building Blocks",
)(secure.secure_cmd)
app.command(
    "conflict",
    help="Inspect one part of the gate in isolation: trigger overlap against existing skills.",
    rich_help_panel="Core Building Blocks",
)(conflict.conflict_cmd)
app.command(
    "test",
    help="Optional live eval workflow against an endpoint. Not required for the default static gate.",
    rich_help_panel="Core Building Blocks",
)(test.test_cmd)
app.command(
    "monitor",
    help="Advanced lifecycle workflow for scheduled health checks and stage transitions.",
    rich_help_panel="Advanced / Secondary",
)(monitor_cmd)
app.add_typer(
    catalog_app,
    name="catalog",
    help="Advanced catalog management commands for YAML skill registries.",
    rich_help_panel="Advanced / Secondary",
)
app.command(
    "fix",
    help="Advanced helper to apply safe automatic fixes where available.",
    rich_help_panel="Advanced / Secondary",
)(fix.fix_cmd)
app.command(
    "suppress",
    help="Advanced helper to record suppressions for intentional findings.",
    rich_help_panel="Advanced / Secondary",
)(suppress_cmd)


if __name__ == "__main__":
    app()
