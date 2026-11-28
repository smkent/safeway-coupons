from __future__ import annotations

import os
from functools import partial
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

from pydantic import SecretStr, TypeAdapter, ValidationError
from rich import print  # noqa: A004
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.style import Style
from rich.table import Table
from rich.text import Text
from typer import Argument, BadParameter, Context, Exit, Option, echo

from safeway_coupons.account import Account, AccountsFile, NotifyConfig
from safeway_coupons.brands import Brand
from safeway_coupons.console import log
from safeway_coupons.errors import AccountLockedError
from safeway_coupons.models.fields import ItemNameT, Password

from .cli import CLI

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    T = TypeVar("T")

cli = CLI(
    name="accounts",
    help="Manage accounts",
    invoke_without_command=False,
    no_args_is_help=True,
)


def _parse_value(parser: Callable[..., T], value: str) -> T:
    try:
        return parser(value)
    except ValueError as e:
        raise BadParameter(str(e)) from e


def require_no_env_account() -> None:
    if Account.load_from_env():
        log.error(
            "Account configured with environment variables"
            " cannot be used with accounts management commands."
        )
        log.error(
            "Unset SAFEWAY_ACCOUNT_USERNAME and SAFEWAY_ACCOUNT_PASSWORD"
            " to use this command."
        )
        raise Exit(1)


def require_accounts_file(ctx: Context) -> None:
    require_no_env_account()
    if ctx.obj.accounts_config:
        log.error(
            "-c/--accounts-config is deprecated"
            " and cannot be used with accounts management commands."
        )
        log.error(
            "Accounts used with -c/--accounts-config can be imported"
            " using the `accounts import` command."
        )
        raise Exit(1)


def load_config_with_account(name: str) -> AccountsFile:
    config = AccountsFile.load(missing_ok=True)
    if name not in config.accounts:
        log.error('No account named "%s" is configured', name)
        raise Exit(1)
    return config


def validate_account_name(name: str) -> str:
    try:
        return TypeAdapter(ItemNameT).validate_python(name)
    except ValidationError as e:
        log.error(
            'Invalid account name "%s": %s',
            name,
            e.errors()[0]["ctx"]["error"],
        )
        raise Exit(1) from e


AccountName = Annotated[
    str, Argument(help="Account name", callback=validate_account_name)
]


def prompt_password() -> str:
    password = Prompt.ask("Sign in password", password=True)
    if password:
        password_confirm = Prompt.ask("Confirm password", password=True)
        if password != password_confirm:
            log.error("Passwords do not match")
            raise Exit(1)
    return password


def prompt_brand() -> Brand:
    while True:
        answer = Prompt.ask("Store brand", default=Brand.Safeway)
        try:
            return Brand(answer)
        except ValueError as e:
            log.error("%s", e)


@cli.command(name="path")
def path() -> None:
    """Show accounts configuration file path."""
    echo(AccountsFile.default_path())


@cli.command(name="list")
@cli.command(name="ls", hidden=True)
def list_command(ctx: Context) -> None:
    """List configured accounts."""
    require_accounts_file(ctx)
    config = AccountsFile.load(missing_ok=True)
    if not config.accounts:
        echo(f"No accounts configured in {config.path}")
        return
    grid = Table.grid(padding=(0, 2), expand=True)
    grid.add_row(
        *(
            Text(t, style="white bold")
            for t in (
                "Name",
                "Brand",
                "Sign in account",
                "Email recipient",
                "Email sender",
            )
        )
    )
    grid.add_row()
    for account in config.accounts.values():
        email = account.notify_email
        grid.add_row(
            Text(account.name, style="bold"),
            account.brand.display_name,
            Text.assemble(
                account.username,
                ""
                if account.password
                else Text(" (no password)", style="yellow"),
            ),
            (
                email.to
                if (email and email.to)
                else Text("(username)", style=Style(dim=True))
            ),
            (
                email.mail_from
                if (email and email.mail_from)
                else Text("(username)", style=Style(dim=True))
            ),
        )
    print(
        Panel(
            grid,
            title=Text(
                "Accounts", style=Style(color="green", bold=True, dim=False)
            ),
            title_align="left",
            expand=False,
            border_style="white dim",
            padding=1,
        )
    )


@cli.command()
def add(
    ctx: Context,
    brand: Annotated[
        Brand | None,
        Argument(
            parser=partial(_parse_value, Brand),
            show_choices=False,
            help="Store brand, choices: " + ", ".join(Brand),
        ),
    ] = None,
    name: Annotated[
        str | None,
        Argument(help="Account name (will be converted to lower case)"),
    ] = None,
    sign_in_email: Annotated[
        str | None, Argument(help="Sign in email address")
    ] = None,
    mail_from: Annotated[
        str | None,
        Option("-f", "--email-from", help="Notification email sender"),
    ] = None,
    mail_to: Annotated[
        str | None,
        Option("-t", "--email-to", help="Notification email recipient"),
    ] = None,
) -> None:
    """Add an account."""
    require_accounts_file(ctx)
    config = AccountsFile.load(missing_ok=True)
    if brand is None:
        brand = prompt_brand()
    if not name:
        name = Prompt.ask("Account name (will be converted to lower case)")
    name = validate_account_name(name)
    if name in config.accounts:
        log.error('An account named "%s" is already configured', name)
        raise Exit(1)
    if not (
        sign_in_email := (sign_in_email or Prompt.ask("Sign in email address"))
    ):
        log.error("Sign in email address is required")
        raise Exit(1)
    password = prompt_password()
    if mail_to is None:
        mail_to = Prompt.ask("Notification email recipient (optional)")
    if mail_from is None:
        mail_from = Prompt.ask("Notification email sender (optional)")
    new_account = Account(
        name=name,
        brand=brand,
        username=sign_in_email,
        password=Password.encode(password) if password else None,
        notify=NotifyConfig.for_email(to=mail_to, mail_from=mail_from),
    )
    config.accounts |= {new_account.name: new_account}
    config.save()
    log.info('Account "%s" saved.', name)


@cli.command(name="import")
def import_command(
    ctx: Context,
    *,
    path: Annotated[
        Path | None,
        Argument(
            help=(
                "Accounts file to import."
                " Defaults to the -c/--accounts-config file."
            ),
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            writable=False,
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        Option(
            "-p",
            "--pretend",
            "--dry-run",
            help="Show accounts that would be imported, but don't save them.",
        ),
    ] = False,
) -> None:
    """Import accounts from a file."""
    require_no_env_account()
    if not (path := path or ctx.obj.accounts_config):
        log.error("No import file specified.")
        raise Exit(1)
    log.info(
        "Importing accounts from %s%s", path, " (dry run)" if dry_run else ""
    )
    accounts_list = (
        list(AccountsFile.load(path).accounts.values())
        if AccountsFile.is_accounts_file(path)
        else Account.load_all_from_config(path)
    )
    config = AccountsFile.load(missing_ok=True)
    imported: dict[str, Account] = {}
    for account in accounts_list:
        if account.name in imported:
            log.warning(
                'Not importing sign in name "%s", since it has the same'
                ' account name "%s" as sign in name "%s"',
                account.username,
                account.name,
                imported[account.name].username,
            )
            continue
        if account.name in config.accounts:
            log.warning(
                'Not importing account "%s", which matches an existing'
                " account",
                account.name,
            )
            continue
        log.info(
            'Importing account "%s" with sign in name "%s"',
            account.name,
            account.username,
        )
        imported[account.name] = account
    if dry_run:
        log.info("Would import %d account(s)", len(imported))
        return
    log.info("Imported %d account(s)", len(imported))
    if not imported:
        return
    config.accounts |= imported
    config.save()
    if path != ctx.obj.accounts_config:
        return
    log.info(
        "Accounts are now configured in %s. %s so it is used.",
        AccountsFile.default_path(),
        "Remove SAFEWAY_ACCOUNTS_FILE and its volume mount"
        if os.environ.get("SAFEWAY_ACCOUNTS_FILE")
        else "Stop passing -c/--accounts-config",
    )


@cli.command(name="set-password")
@cli.command(name="password", hidden=True)
def set_password(ctx: Context, *, name: AccountName) -> None:
    """Set an account password."""
    require_accounts_file(ctx)
    config = load_config_with_account(name)
    if not (password := prompt_password()):
        log.error(
            "No password entered."
            " To remove a saved password,"
            " use the `accounts clear-password` command."
        )
        raise Exit(1)
    config.accounts[name].password = SecretStr(password)
    config.save()
    log.info('Account "%s" password set.', name)


@cli.command(name="clear-password")
def clear_password(
    ctx: Context,
    *,
    name: AccountName,
    yes: Annotated[
        bool, Option("-y", "--yes", help="Skip confirmation prompts.")
    ] = False,
) -> None:
    """Clear an account password."""
    require_accounts_file(ctx)
    config = load_config_with_account(name)
    if not config.accounts[name].password:
        log.info('Account "%s" has no password set.', name)
        return
    if not (
        yes
        or Confirm.ask(
            (
                "Are you sure you want to remove the saved password"
                f' for the "{name}" account?'
            ),
            default=False,
        )
    ):
        return
    config.accounts[name].password = None
    config.save()
    log.info('Account "%s" password cleared.', name)


@cli.command(name="rename")
@cli.command(name="mv", hidden=True)
def rename(
    ctx: Context,
    *,
    name: AccountName,
    new_name: Annotated[
        str,
        Argument(help="New account name (will be converted to lower case)"),
    ],
) -> None:
    """Rename an account, along with its saved browser state."""
    require_accounts_file(ctx)
    config = load_config_with_account(name)
    new_name = validate_account_name(new_name)
    if new_name in config.accounts:
        log.error('An account named "%s" is already configured', new_name)
        raise Exit(1)
    account = config.accounts[name]
    # Not model_copy(), which would also copy cached state paths
    renamed = Account.model_validate(
        {**account.model_dump(exclude_unset=True), "name": new_name}
    )
    if renamed.state_dir.exists():
        log.error(
            "%s already exists. Move or delete it, then try again.",
            renamed.state_dir,
        )
        raise Exit(1)
    try:
        # Hold the lock so a run can't use the state while it moves
        with account.lock:
            account.state_dir.rename(renamed.state_dir)
            try:
                config.rename_account(name, renamed)
            except Exception:
                renamed.state_dir.rename(account.state_dir)
                raise
    except AccountLockedError as e:
        log.error("%s, try again later", e)
        raise Exit(1) from e
    log.info('Account "%s" renamed to "%s".', name, new_name)


@cli.command(name="remove")
@cli.command(name="rm", hidden=True)
def remove(
    ctx: Context,
    *,
    name: AccountName,
    yes: Annotated[
        bool, Option("-y", "--yes", help="Skip confirmation prompts.")
    ] = False,
) -> None:
    """Remove an account."""
    require_accounts_file(ctx)
    config = load_config_with_account(name)
    if not (
        yes
        or Confirm.ask(
            f'Are you sure you want to remove the "{name}" account?',
            default=False,
        )
    ):
        return
    account = config.accounts.pop(name)
    if config.accounts:
        config.save()
    else:
        config.delete()
    log.info('Account "%s" removed.', name)
    if account.state_dir.exists():
        log.info(
            'Saved browser state for "%s" was kept at %s.'
            " Delete it if you no longer need it.",
            name,
            account.state_dir,
        )
