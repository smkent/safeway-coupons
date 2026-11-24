from __future__ import annotations

import shlex
from pathlib import Path  # noqa: TC003
from typing import Annotated

from typer import Context, Exit, Option

from safeway_coupons import version as package_version
from safeway_coupons.app import SafewayCoupons
from safeway_coupons.console import console, log
from safeway_coupons.dirs import dirs

from .cli import CLI
from .storage import cli as cli_storage

cli = CLI(
    help='Automatic coupon clipper for "Safeway for U" coupons',
    invoke_without_command=True,
)
cli.add_typer(cli_storage)


class HelpPanel:
    ADVANCED = "Advanced options"


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
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            writable=False,
            help=(
                "Path to configuration file containing Safeway "
                "accounts information."
            ),
        ),
    ] = None,
    debug: Annotated[
        int, Option("-d", "--debug", count=True, hidden=True)
    ] = 0,
    verbose: Annotated[
        int,
        Option(
            "-v", "--verbose", count=True, help="Increase logging verbosity."
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
    sendmail: Annotated[
        str,
        Option(
            "--sendmail",
            help=(
                "Path to sendmail and any additional arguments to use when "
                "sending email."
            ),
            rich_help_panel=HelpPanel.ADVANCED,
        ),
    ] = "/usr/sbin/sendmail",
    login_only: Annotated[
        bool,
        Option(
            "--login-only",
            help="Sign in to each account without clipping any coupons.",
        ),
    ] = False,
    storage_dir: Annotated[
        Path | None,
        Option(
            "--storage-dir",
            envvar="SAFEWAY_COUPONS_STORAGE_DIR",
            help=(
                "Base directory for configuration and"
                " persistent state storage."
            ),
            rich_help_panel=HelpPanel.ADVANCED,
        ),
    ] = None,
) -> None:
    if version_option:
        version()
        raise Exit
    if storage_dir:
        dirs.base = storage_dir.resolve()
    console.configure(verbose=(verbose or debug))
    if debug:
        log.warning("-d/--debug is deprecated, use -v/--verbose instead")
    if ctx.invoked_subcommand:
        return
    SafewayCoupons(
        send_email=send_email,
        sendmail=shlex.split(sendmail) if sendmail else None,
        sleep_level=sleep_level,
        dry_run=dry_run,
        max_clip_count=max_clip_count,
        continue_on_error=continue_on_error,
        headless=headless,
        accounts_config=accounts_config,
        login_only=login_only,
    )()


@cli.command(help=f"Show version ({package_version}) and exit.")
def version() -> None:
    print(package_version)  # noqa: T201
