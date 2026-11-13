from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from safeway_coupons.safeway import SafewayCoupons

if TYPE_CHECKING:
    from pathlib import Path


def app(
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
