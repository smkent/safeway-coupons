from __future__ import annotations

import logging
import random
import sys
import time
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from .account import Account
from .client.auth import LoginSession
from .client.client import SafewayClient
from .console import log
from .email import email_clip_results, email_error
from .errors import ClipError, Error, TooManyClipErrors
from .models.safeway.offers import Offer, OfferStatus, OfferType

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence
    from pathlib import Path
    from typing import TypeVar

    T = TypeVar("T")

CLIP_ERROR_MAX = 5


@dataclass
class SafewayCoupons:
    sleep_level: int = field(default=0, kw_only=True)
    max_clip_count: int = field(default=0, kw_only=True)
    max_clip_errors: int = field(default=CLIP_ERROR_MAX, kw_only=True)
    continue_on_error: bool = field(default=False, kw_only=True)
    send_email: bool = field(default=True, kw_only=True)
    dry_run: bool = field(default=False, kw_only=True)
    headless: bool = field(default=True, kw_only=True)
    sendmail: Sequence[str] | None = field(default=None, kw_only=True)
    accounts_config: Path | None = field(default=None, kw_only=True)
    login_only: bool = field(default=False, kw_only=True)
    account_names: Sequence[str] = field(default=(), kw_only=True)

    @cached_property
    def accounts(self) -> Sequence[Account]:
        all_accounts = Account.load_all(config_file=self.accounts_config)
        if not self.account_names:
            return all_accounts
        accounts_by_name = {a.name: a for a in all_accounts}
        names = list(dict.fromkeys(n.lower() for n in self.account_names))
        if unknown_names := [n for n in names if n not in accounts_by_name]:
            for name in unknown_names:
                log.error('No account named "%s" is configured', name)
            sys.exit(1)
        return [accounts_by_name[n] for n in names]

    @cached_property
    def sendmail_path(self) -> Sequence[str]:
        return self.sendmail or ["/usr/sbin/sendmail"]

    def __call__(self) -> None:
        if not self.accounts:
            log.error("No Safeway accounts configured")
            sys.exit(1)
        errors = 0
        for account in self.accounts:
            if not self.run_for_account(account):
                errors += 1
                if not (self.login_only or self.continue_on_error):
                    break
        if errors:
            action = "signing in" if self.login_only else "clipping coupons"
            log.error("Error %s for %s accounts", action, errors)
            sys.exit(1)

    def run_for_account(self, account: Account) -> bool:
        try:
            with account.lock:
                if self.login_only:
                    self.login_for_account(account)
                else:
                    self.clip_for_account(account)
        except Error as e:
            log.error(
                "Error for account %s: %s",
                account.username,
                e,
                exc_info=log.isEnabledFor(logging.DEBUG),
            )
            return False
        return True

    def login_for_account(self, account: Account) -> None:
        action = "Checking sign in" if self.dry_run else "Signing in"
        log.info("%s for Safeway account %s", action, account.username)
        LoginSession(account, headless=self.headless, dry_run=self.dry_run)

    def clip_for_account(self, account: Account) -> None:
        log.info("Clipping coupons for Safeway account %s", account.username)
        try:
            swy = SafewayClient(account, headless=self.headless)
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
                log.warning(
                    "Skipping %d offers with unknown offer types",
                    unknown_count,
                )
            if not unclipped_offers:
                log.info("Nothing to do")
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
                    log.info("%s clipped %s Clipped", progress_count, offer)
                    clipped_offers.append(offer)
                    if (
                        self.max_clip_count
                        and len(clipped_offers) >= self.max_clip_count
                    ):
                        log.info(
                            "Clip maximum count of %d reached",
                            self.max_clip_count,
                        )
                        break
                except ClipError as e:
                    log.info("%s %s", progress_count, e)
                    clip_errors.append(e)
                    if (
                        self.max_clip_errors
                        and len(clip_errors) >= self.max_clip_errors
                    ):
                        raise TooManyClipErrors(
                            clipped_offers=clipped_offers,
                            errors=clip_errors,
                        ) from e

            log.info("Clipped %d coupons", len(clipped_offers))
            email_clip_results(
                self.sendmail_path,
                account,
                clipped_offers,
                send_email=self.send_email and not self.dry_run,
            )
        except Error as e:
            email_error(
                self.sendmail_path,
                account,
                error=e,
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
                if delay_time >= 1:
                    log.debug("Waiting %d seconds", delay_time)
                time.sleep(delay_time)
            yield item
