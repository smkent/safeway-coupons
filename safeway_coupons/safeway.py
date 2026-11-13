from __future__ import annotations

from typing import TYPE_CHECKING

from .client import SafewayClient
from .email import email_clip_results, email_error
from .errors import ClipError, Error, TooManyClipErrors
from .models.safeway import Offer, OfferStatus, OfferType
from .utils import yield_delay

if TYPE_CHECKING:
    from .accounts import Account

CLIP_ERROR_MAX = 5


class SafewayCoupons:
    def __init__(
        self,
        sendmail: list[str] | None = None,
        debug_level: int = 0,
        sleep_level: int = 0,
        max_clip_count: int = 0,
        max_clip_errors: int = CLIP_ERROR_MAX,
        *,
        send_email: bool = True,
        dry_run: bool = False,
        headless: bool = True,
    ) -> None:
        self.send_email = send_email
        self.sendmail = sendmail or ["/usr/sbin/sendmail"]
        self.debug_level = debug_level
        self.sleep_level = sleep_level
        self.dry_run = dry_run
        self.max_clip_count = max_clip_count
        self.max_clip_errors = max_clip_errors
        self.headless = headless

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
            for i, offer in enumerate(
                yield_delay(
                    unclipped_offers, self.sleep_level, self.debug_level
                )
            ):
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
                            e,
                            clipped_offers=clipped_offers,
                            errors=clip_errors,
                        ) from e

            print(f"Clipped {len(clipped_offers)} coupons")  # noqa: T201
            email_clip_results(
                self.sendmail,
                account,
                clipped_offers,
                debug_level=self.debug_level,
                send_email=self.send_email and not self.dry_run,
            )
        except Error as e:
            email_error(
                self.sendmail,
                account,
                error=e,
                debug_level=self.debug_level,
                send_email=self.send_email and not self.dry_run,
            )
            raise
