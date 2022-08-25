import argparse
import sys
from http.client import HTTPConnection
from typing import List

from .accounts import Account
from .client import SafewayClient
from .config import Config
from .email import email_clip_results, email_error
from .errors import ClipError, Error, TooManyClipErrors
from .models import Offer, OfferStatus
from .utils import yield_delay

CLIP_ERROR_MAX = 5


def parse_args() -> argparse.Namespace:
    description = 'Automatic coupon clipper for "Safeway for U" coupons'
    arg_parser = argparse.ArgumentParser(description=description)
    arg_parser.add_argument(
        "-c",
        "--accounts-config",
        dest="accounts_config",
        metavar="file",
        help=(
            "Path to configuration file containing Safeway "
            "accounts information"
        ),
    )
    arg_parser.add_argument(
        "-d",
        "--debug",
        dest="debug_level",
        action="count",
        default=0,
        help=(
            "Print debugging information on stdout. Specify "
            "twice to increase verbosity."
        ),
    )
    arg_parser.add_argument(
        "-n",
        "--no-email",
        dest="send_email",
        action="store_false",
        help="Don't send results email",
    )
    arg_parser.add_argument(
        "-p",
        "--pretend",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print coupons that would be clipped, but don't clip them",
    )
    arg_parser.add_argument(
        "-S",
        "--no-sleep",
        "--no-delay",
        dest="sleep_level",
        action="count",
        default=0,
        help=(
            "Don't wait between long requests. Specify twice to never wait."
        ),
    )
    return arg_parser.parse_args()


def clip_for_account(args: argparse.Namespace, account: Account) -> None:
    print(f"Clipping coupons for Safeway account {account.username}")
    swy = SafewayClient(account)
    clipped_offers: List[Offer] = []
    clip_errors: List[ClipError] = []
    offers = swy.get_offers()
    unclipped_offers = [o for o in offers if o.status == OfferStatus.Unclipped]
    rjust_size = len(str(len(unclipped_offers)))
    for i, offer in enumerate(
        yield_delay(unclipped_offers, args.sleep_level, args.debug_level)
    ):
        progress_count = (
            f"({str(i + 1).rjust(rjust_size, ' ')}"
            f"/{len(unclipped_offers)}) "
        )
        try:
            if not args.dry_run:
                swy.clip(offer)
            print(f"{progress_count} Clipped {offer}")
            clipped_offers.append(offer)
        except ClipError as e:
            print(f"{progress_count} {e}")
            clip_errors.append(e)
            if len(clip_errors) >= CLIP_ERROR_MAX:
                raise TooManyClipErrors(
                    e, clipped_offers=clipped_offers, errors=clip_errors
                )

    print(f"Clipped {len(clipped_offers)} coupons")
    email_clip_results(
        account,
        clipped_offers,
        error=None,
        clip_errors=clip_errors,
        debug_level=args.debug_level,
        send_email=args.send_email,
    )


def v2() -> None:
    args = parse_args()
    if args.debug_level >= 2:
        HTTPConnection.debuglevel = 1
    try:
        accounts = Config.load_accounts(config_file=args.accounts_config)
        for account in accounts:
            try:
                clip_for_account(args, account)
            except Error as e:
                email_error(
                    account,
                    error=e,
                    debug_level=args.debug_level,
                    send_email=args.send_email,
                )
                raise
    except Exception as e:
        if args.debug_level:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
