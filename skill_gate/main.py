"""skill-gate CLI entrypoint."""

from __future__ import annotations

import importlib.metadata

import typer

from skill_gate.commands import conflict, init, secure, test, validate
from skill_gate.commands.catalog import catalog_app
from skill_gate.commands.check import check_cmd

app = typer.Typer(name="skill-gate", help="The quality gate for Agent Skills.")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(None, "--version", help="Show version and exit"),
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
app.command("test")(test.test_cmd)
app.add_typer(catalog_app, name="catalog")
app.command("check")(check_cmd)


if __name__ == "__main__":
    app()
