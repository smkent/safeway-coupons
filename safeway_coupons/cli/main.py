from __future__ import annotations

import shlex
import sys
from pathlib import Path  # noqa: TC003
from typing import Annotated

from typer import Context, Exit, Option, echo

from safeway_coupons import version as package_version
from safeway_coupons.account import AccountsFile
from safeway_coupons.app import SafewayCoupons
from safeway_coupons.console import console, log
from safeway_coupons.dirs import dirs

from .accounts import cli as cli_accounts
from .cli import CLI, CLIContext
from .storage import cli as cli_storage

cli = CLI(
    help='Automatic coupon clipper for "Safeway for U" coupons',
    invoke_without_command=True,
)
cli.add_typer(cli_accounts)
cli.add_typer(cli_accounts, name="account", hidden=True)
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
            hidden=True,
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            writable=False,
        ),
    ] = None,
    debug: Annotated[
        int, Option("-d", "--debug", count=True, hidden=True)
    ] = 0,
    no_email: Annotated[
        bool,
        Option("--no-email", show_default=False, hidden=True),
    ] = False,
    verbose: Annotated[
        int,
        Option(
            "-v", "--verbose", count=True, help="Increase logging verbosity."
        ),
    ] = 0,
    account_names: Annotated[
        list[str] | None,
        Option(
            "-a",
            "--account",
            metavar="<str>",
            envvar="SAFEWAY_COUPONS_ACCOUNTS",
            show_default="All accounts",
            show_envvar=False,
            help="Account name (may be used multiple times).",
        ),
    ] = None,
    max_clip_count: Annotated[
        int,
        Option(
            "-m",
            "--max-clip",
            help="Maximum number of coupons to clip (default 0 means all).",
        ),
    ] = 0,
    notify: Annotated[
        bool | None,
        Option(
            "-N/-n",
            "--notify/--no-notify",
            show_default="Notify when run non-interactively",
            help="Send results notification (email).",
        ),
    ] = None,
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
    ctx.obj = CLIContext(accounts_config=accounts_config)
    if version_option:
        version()
        raise Exit
    if storage_dir:
        dirs.base = storage_dir
    console.configure(verbose=(verbose or debug))
    if debug:
        log.warning("-d/--debug is deprecated, use -v/--verbose instead")
    if accounts_config:
        log.warning(
            "-c/--accounts-config is deprecated and will be removed"
            " in a future release. Migrate your accounts to %s.",
            AccountsFile.default_path(),
        )
    if ctx.invoked_subcommand:
        return
    if no_email:
        log.warning("--no-email is deprecated, use -n/--no-notify instead")
    if notify is None:
        notify = not sys.stdin.isatty()
    SafewayCoupons(
        send_email=notify and not no_email,
        sendmail=shlex.split(sendmail) if sendmail else None,
        sleep_level=sleep_level,
        dry_run=dry_run,
        max_clip_count=max_clip_count,
        continue_on_error=continue_on_error,
        headless=headless,
        accounts_config=accounts_config,
        login_only=login_only,
        account_names=account_names or (),
    )()


@cli.command(help=f"Show version ({package_version}) and exit.")
def version() -> None:
    echo(package_version)
