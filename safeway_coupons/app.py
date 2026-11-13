from __future__ import annotations

import shlex
import sys
import traceback
from http.client import HTTPConnection
from typing import TYPE_CHECKING

from .account import Account
from .config import config
from .errors import Error
from .safeway import SafewayCoupons

if TYPE_CHECKING:
    from pathlib import Path


def main(
    *,
    accounts_config: Path | None = None,
    debug_level: int = 0,
    max_clip_count: int = 0,
    sendmail: str | None = None,
    send_email: bool = True,
    dry_run: bool = False,
    sleep_level: int = 0,
    continue_on_error: bool = False,
    headless: bool = True,
    state_dir: Path | None = None,
) -> None:
    if state_dir:
        config.state_dir = state_dir
    accounts = Account.load_all(config_file=accounts_config)
    if not accounts:
        print("Error: No Safeway account(s) configured", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    if debug_level >= 2:
        HTTPConnection.debuglevel = 1
    sc = SafewayCoupons(
        send_email=send_email,
        sendmail=shlex.split(sendmail) if sendmail else None,
        debug_level=debug_level,
        sleep_level=sleep_level,
        dry_run=dry_run,
        max_clip_count=max_clip_count,
        headless=headless,
    )
    errors = 0
    try:
        for account in accounts:
            try:
                with account:
                    sc.clip_for_account(account)
            except Error:
                if not continue_on_error:
                    raise
                traceback.print_exc()
                errors += 1
        if errors:
            print(f"Error clipping coupons for {errors} account(s)")  # noqa: T201
            sys.exit(1)
    except Exception as e:
        if debug_level:
            raise
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
