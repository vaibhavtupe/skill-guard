"""skill-guard CLI entrypoint."""

from __future__ import annotations

import importlib.metadata

import typer

from skill_guard.commands import conflict, fix, init, secure, validate
from skill_guard.commands.check import check_cmd
from skill_guard.commands.suppress import suppress_cmd

app = typer.Typer(
    name="skill-guard",
    help=(
        "The quality gate for Agent Skills.\n\n"
        "Start with `skill-guard check <skill-or-skills-root>` for the default pre-merge workflow."
    ),
    no_args_is_help=True,
)


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


# Register subcommands
app.command(
    "check",
    help="Default gate: run validate + secure + conflict.",
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
