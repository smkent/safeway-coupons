from __future__ import annotations

import random
import sys
import time
import traceback
from dataclasses import InitVar, dataclass, field
from functools import cached_property
from http.client import HTTPConnection
from typing import TYPE_CHECKING

from .account import Account
from .client.client import SafewayClient
from .config import config
from .email import email_clip_results, email_error
from .errors import ClipError, Error, TooManyClipErrors
from .models.safeway import Offer, OfferStatus, OfferType

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence
    from pathlib import Path
    from typing import TypeVar

    T = TypeVar("T")

CLIP_ERROR_MAX = 5


@dataclass
class SafewayCoupons:
    debug_level: int = field(default=0, kw_only=True)
    sleep_level: int = field(default=0, kw_only=True)
    max_clip_count: int = field(default=0, kw_only=True)
    max_clip_errors: int = field(default=CLIP_ERROR_MAX, kw_only=True)
    continue_on_error: bool = field(default=False, kw_only=True)
    send_email: bool = field(default=True, kw_only=True)
    dry_run: bool = field(default=False, kw_only=True)
    headless: bool = field(default=True, kw_only=True)
    sendmail: Sequence[str] | None = field(default=None, kw_only=True)
    accounts_config: InitVar[Path | None] = field(default=None, kw_only=True)
    state_dir: InitVar[Path | None] = field(default=None, kw_only=True)
    accounts: Sequence[Account] = field(default=(), kw_only=True, init=False)

    def __post_init__(
        self, accounts_config: Path | None, state_dir: Path | None
    ) -> None:
        if state_dir:
            config.state_dir = state_dir
        self.accounts = Account.load_all(config_file=accounts_config)

    @cached_property
    def sendmail_path(self) -> Sequence[str]:
        return self.sendmail or ["/usr/sbin/sendmail"]

    def __call__(self) -> None:
        if not self.accounts:
            print("Error: No Safeway account(s) configured", file=sys.stderr)  # noqa: T201
            sys.exit(1)
        if self.debug_level >= 2:
            HTTPConnection.debuglevel = 1
        errors = 0
        try:
            for account in self.accounts:
                try:
                    with account.lock:
                        self.clip_for_account(account)
                except Error:
                    if not self.continue_on_error:
                        raise
                    traceback.print_exc()
                    errors += 1
            if errors:
                print(f"Error clipping coupons for {errors} account(s)")  # noqa: T201
                sys.exit(1)
        except Exception as e:
            if self.debug_level:
                raise
            print(f"Error: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(1)

    def clip_for_account(self, account: Account) -> None:
        print(f"Clipping coupons for Safeway account {account.username}")  # noqa: T201
        try:
            swy = SafewayClient(
                account, headless=self.headless, debug_level=self.debug_level
            )
            clipped_offers: list[Offer] = []
            clip_errors: list[ClipError] = []
            offers = swy.get_offers()
            all_unclipped_offers = [
                o
                for o in offers.offers.values()
                if o.status == OfferStatus.Unclipped
            ]
            unclipped_offers = [
                o
                for o in all_unclipped_offers
                if isinstance(o.offer_pgm, OfferType)
            ]
            if unknown_count := (
                len(all_unclipped_offers) - len(unclipped_offers)
            ):
                print(  # noqa: T201
                    f"Skipping {unknown_count} offers with unknown offer types"
                )
            if not unclipped_offers:
                print("Nothing to do")  # noqa: T201
                return
            rjust_size = len(str(len(unclipped_offers)))
            for i, offer in enumerate(self.yield_delay(unclipped_offers)):
                progress_count = (
                    f"({str(i + 1).rjust(rjust_size, ' ')}"
                    f"/{len(unclipped_offers)}) "
                )
                try:
                    if not self.dry_run:
                        swy.clip(offer)
                    print(f"{progress_count} Clipped {offer}")  # noqa: T201
                    clipped_offers.append(offer)
                    if (
                        self.max_clip_count
                        and len(clipped_offers) >= self.max_clip_count
                    ):
                        print(  # noqa: T201
                            "Clip maximum count of "
                            f"{self.max_clip_count} reached"
                        )
                        break
                except ClipError as e:
                    print(f"{progress_count} {e}")  # noqa: T201
                    clip_errors.append(e)
                    if (
                        self.max_clip_errors
                        and len(clip_errors) >= self.max_clip_errors
                    ):
                        raise TooManyClipErrors(
                            clipped_offers=clipped_offers,
                            errors=clip_errors,
                        ) from e

            print(f"Clipped {len(clipped_offers)} coupons")  # noqa: T201
            email_clip_results(
                self.sendmail_path,
                account,
                clipped_offers,
                debug_level=self.debug_level,
                send_email=self.send_email and not self.dry_run,
            )
        except Error as e:
            email_error(
                self.sendmail_path,
                account,
                error=e,
                debug_level=self.debug_level,
                send_email=self.send_email and not self.dry_run,
            )
            raise

    def yield_delay(self, iterable: Iterable[T]) -> Generator[T, None, None]:
        for count, item in enumerate(iterable):
            delay_time = 0.0
            if self.sleep_level < 2:
                if self.sleep_level < 1 and count and count % 12 == 0:
                    if count % 48 == 0:
                        delay_time = random.uniform(15.0, 25.0)  # noqa: S311
                    else:
                        delay_time = random.uniform(4.0, 8.0)  # noqa: S311
                    delay_time = round(delay_time, 2)
                else:
                    delay_time = random.uniform(0.3, 0.8)  # noqa: S311
            if delay_time:
                if self.debug_level >= 1 and delay_time >= 1:
                    print(f"Waiting {delay_time} seconds")  # noqa: T201
                time.sleep(delay_time)
            yield item
