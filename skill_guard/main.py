"""skill-guard CLI entrypoint."""

from __future__ import annotations

import importlib.metadata

import typer

from skill_guard.commands import conflict, init, secure, test, validate
from skill_guard.commands.catalog import catalog_app
from skill_guard.commands.check import check_cmd
from skill_guard.commands.monitor import monitor_cmd

app = typer.Typer(name="skill-guard", help="The quality gate for Agent Skills.")


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
    """The quality gate for Agent Skills."""


# Register subcommands
app.command("validate")(validate.validate_cmd)
app.command("secure")(secure.secure_cmd)
app.command("conflict")(conflict.conflict_cmd)
app.command("init")(init.init_cmd)
app.command("test")(test.test_cmd)
app.command("monitor")(monitor_cmd)
app.add_typer(catalog_app, name="catalog")
app.command("check")(check_cmd)


if __name__ == "__main__":
    app()
