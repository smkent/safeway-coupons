import argparse
import sys
from http.client import HTTPConnection

from .config import Config
from .safeway import SafewayCoupons


def _parse_args() -> argparse.Namespace:
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
        "-m",
        "--max-clip",
        dest="max_clip_count",
        type=int,
        default=0,
        metavar="number",
        help="Maximum number of coupons to clip (default: all)",
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


def main() -> None:
    args = _parse_args()
    accounts = Config.load_accounts(config_file=args.accounts_config)
    if not accounts:
        print("Error: No Safeway account(s) configured", file=sys.stderr)
        sys.exit(1)
    if args.debug_level >= 2:
        HTTPConnection.debuglevel = 1
    sc = SafewayCoupons(
        send_email=args.send_email,
        debug_level=args.debug_level,
        sleep_level=args.sleep_level,
        dry_run=args.dry_run,
        max_clip_count=args.max_clip_count,
    )
    try:
        for account in accounts:
            sc.clip_for_account(account)
    except Exception as e:
        if args.debug_level:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
