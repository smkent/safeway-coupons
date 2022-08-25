from typing import List

from .accounts import Account
from .client import SafewayClient
from .email import email_clip_results, email_error
from .errors import ClipError, Error, TooManyClipErrors
from .models import Offer, OfferStatus
from .utils import yield_delay


class SafewayCoupons:
    CLIP_ERROR_MAX = 5

    def __init__(
        self,
        send_email: bool = True,
        debug_level: int = 0,
        sleep_level: int = 0,
        dry_run: bool = False,
        max_clip: int = 0,
    ) -> None:
        self.send_email = send_email
        self.debug_level = debug_level
        self.sleep_level = sleep_level
        self.dry_run = dry_run
        self.max_clip = max_clip

    def clip_for_account(self, account: Account) -> None:
        print(f"Clipping coupons for Safeway account {account.username}")
        swy = SafewayClient(account)
        clipped_offers: List[Offer] = []
        clip_errors: List[ClipError] = []
        try:
            offers = swy.get_offers()
            unclipped_offers = [
                o for o in offers if o.status == OfferStatus.Unclipped
            ]
            if not unclipped_offers:
                print("Nothing to do")
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
                    print(f"{progress_count} Clipped {offer}")
                    clipped_offers.append(offer)
                    if self.max_clip and len(clipped_offers) >= self.max_clip:
                        print(f"Clip maximum count of {self.max_clip} reached")
                        break
                except ClipError as e:
                    print(f"{progress_count} {e}")
                    clip_errors.append(e)
                    if len(clip_errors) >= self.CLIP_ERROR_MAX:
                        raise TooManyClipErrors(
                            e,
                            clipped_offers=clipped_offers,
                            errors=clip_errors,
                        )

            print(f"Clipped {len(clipped_offers)} coupons")
            email_clip_results(
                account,
                clipped_offers,
                error=None,
                clip_errors=clip_errors,
                debug_level=self.debug_level,
                send_email=self.send_email,
            )
        except Error as e:
            email_error(
                account,
                error=e,
                debug_level=self.debug_level,
                send_email=self.send_email,
            )
            raise
