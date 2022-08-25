import argparse
import sys
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
        dest="debug",
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
    print(account)
    swy = SafewayClient(account)
    clipped_offers: List[Offer] = []
    clip_errors: List[ClipError] = []
    offers = swy.get_offers()
    unclipped_offers = [o for o in offers if o.status == OfferStatus.Unclipped]
    for offer in yield_delay(unclipped_offers, args.sleep_level):
        try:
            if not args.dry_run:
                swy.clip(offer)
            print(f"Clipped {offer}")
            clipped_offers.append(offer)
        except ClipError as e:
            print(e)
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
        debug=args.debug,
        send_email=args.send_email,
    )


def v2() -> None:
    args = parse_args()
    try:
        accounts = Config.load_accounts(config_file=args.accounts_config)
        for account in accounts:
            try:
                clip_for_account(args, account)
            except Error as e:
                email_error(
                    account,
                    error=e,
                    debug=args.debug,
                    send_email=args.send_email,
                )
                raise
    except Exception as e:
        if args.debug:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
