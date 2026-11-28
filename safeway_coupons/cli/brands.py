from __future__ import annotations

from rich import print  # noqa: A004
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text

from safeway_coupons.brands import Brand

from .cli import CLI

cli = CLI(
    name="brands",
    help="Show store brands",
    invoke_without_command=False,
    no_args_is_help=True,
)


@cli.command(name="list")
@cli.command(name="ls", hidden=True)
def list_command() -> None:
    """List supported store brands."""
    grid = Table.grid(padding=(0, 2), expand=True)
    grid.add_row(
        *(
            Text(t, style="white bold")
            for t in ("Name", "Account brand setting")
        )
    )
    grid.add_row()
    for brand in sorted(Brand, key=lambda b: b.display_name):
        grid.add_row(
            Text.assemble(
                Text(
                    brand.display_name,
                    style=Style(bold=True, link=brand.origin),
                ),
            ),
            brand.value,
        )
    print(
        Panel(
            grid,
            title=Text(
                "Supported store brands",
                style=Style(color="sky_blue1", bold=True, dim=False),
            ),
            title_align="left",
            expand=False,
            border_style="sky_blue1 dim",
            padding=1,
        )
    )
