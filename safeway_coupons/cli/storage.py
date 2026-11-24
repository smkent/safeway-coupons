from __future__ import annotations

from typing import Annotated, Literal

from typer import Argument

from safeway_coupons.dirs import dirs

from .cli import CLI

cli = CLI(
    name="storage",
    help="Manage storage",
    invoke_without_command=False,
    no_args_is_help=True,
)


@cli.command(name="list")
@cli.command(name="ls", hidden=True)
def list_command() -> None:
    """List storage directory paths."""
    print("State:", dirs.state)  # noqa: T201


@cli.command(name="show")
def show(
    name: Annotated[Literal["state"], Argument(help="Storage path type")],
) -> None:
    """Show specified storage directory path."""
    print(getattr(dirs, name))  # noqa: T201
