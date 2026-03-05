"""skill-gate CLI entrypoint."""
from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Optional

import typer

from skill_gate.commands import conflict, init, secure, validate

app = typer.Typer(name="skill-gate", help="The quality gate for Agent Skills.")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(None, "--version", help="Show version and exit"),
):
    if version:
        v = importlib.metadata.version("skill-gate")
        typer.echo(v)
        raise typer.Exit()


# Register subcommands
app.command("validate")(validate.validate_cmd)
app.command("secure")(secure.secure_cmd)
app.command("conflict")(conflict.conflict_cmd)
app.command("init")(init.init_cmd)


if __name__ == "__main__":
    app()
