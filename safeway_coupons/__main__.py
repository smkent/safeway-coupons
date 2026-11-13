from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path  # noqa: TC003
from typing import Annotated

from typer import Context, Exit, Option, Typer

from . import version as package_version
from .safeway import SafewayCoupons

cli = Typer(
    help='Automatic coupon clipper for "Safeway for U" coupons',
    add_completion=False,
    pretty_exceptions_enable=False,
    invoke_without_command=True,
)


@cli.callback()
def setup(
    ctx: Context,
    *,
    version_option: Annotated[
        bool, Option("-V", "--version", hidden=True)
    ] = False,
    accounts_config: Annotated[
        Path | None,
        Option(
            "-c",
            "--accounts-config",
            help=(
                "Path to configuration file containing Safeway "
                "accounts information."
            ),
        ),
    ] = None,
    debug_level: Annotated[
        int,
        Option(
            "-d",
            "--debug",
            count=True,
            help=(
                "Print debugging information on stdout. Specify "
                "twice to increase verbosity."
            ),
        ),
    ] = 0,
    max_clip_count: Annotated[
        int,
        Option(
            "-m",
            "--max-clip",
            help="Maximum number of coupons to clip (default 0 means all).",
        ),
    ] = 0,
    sendmail: Annotated[
        str,
        Option(
            "--sendmail",
            help=(
                "Path to sendmail and any additional arguments to use when "
                "sending email."
            ),
        ),
    ] = "/usr/sbin/sendmail",
    send_email: Annotated[
        bool,
        Option(
            " /-n",
            " /--no-email",
            show_default=False,
            help="Don't send results email.",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        Option(
            "-p",
            "--pretend",
            "--dry-run",
            help="Print coupons that would be clipped, but don't clip them.",
        ),
    ] = False,
    sleep_level: Annotated[
        int,
        Option(
            "-S",
            "--no-sleep",
            "--no-delay",
            count=True,
            help=(
                "Don't wait between long requests."
                " Specify twice to never wait."
            ),
        ),
    ] = 0,
    continue_on_error: Annotated[
        bool,
        Option(
            "-E",
            "--continue-on-error",
            help="Continue clipping coupons for the next account on error.",
        ),
    ] = False,
    headless: Annotated[
        bool,
        Option(
            " /-H",
            " /--no-headless",
            show_default=False,
            help="Run with browser visible (disable headless mode)",
        ),
    ] = True,
    state_dir: Annotated[
        Path | None,
        Option(
            "-s",
            "--state-dir",
            help="Directory for persistent state such as browser profiles.",
        ),
    ] = None,
) -> None:
    if version_option:
        version()
        raise Exit
    if ctx.invoked_subcommand:
        return
    SafewayCoupons(
        send_email=send_email,
        sendmail=shlex.split(sendmail) if sendmail else None,
        debug_level=debug_level,
        sleep_level=sleep_level,
        dry_run=dry_run,
        max_clip_count=max_clip_count,
        continue_on_error=continue_on_error,
        headless=headless,
        accounts_config=accounts_config,
        state_dir=state_dir,
    )()


@cli.command(help=f"Show version ({package_version}) and exit.")
def version() -> None:
    print(package_version)  # noqa: T201


def setup_env() -> None:
    os.environ.setdefault(
        "TERMINAL_WIDTH", str(min(shutil.get_terminal_size().columns, 160))
    )


def main() -> None:
    setup_env()
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
