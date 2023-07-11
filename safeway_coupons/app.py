import argparse
import shlex
import sys
import traceback
from http.client import HTTPConnection
from pathlib import Path

from .config import Config
from .errors import Error
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
        "-D",
        "--debug-dir",
        dest="debug_dir",
        metavar="directory",
        default=".",
        help=(
            "Destination directory for debug output files, "
            "such as browser screenshots (default: %(default)s)"
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
        "--sendmail",
        metavar="path/to/sendmail",
        dest="sendmail",
        type=shlex.split,
        default="/usr/sbin/sendmail",
        help=(
            "Path to sendmail and any additional arguments to use when "
            "sending email (default: %(default)s)"
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
    arg_parser.add_argument(
        "-E",
        "--continue-on-error",
        dest="continue_on_error",
        action="store_true",
        help="Continue clipping coupons for the next account on error",
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
        sendmail=args.sendmail,
        debug_level=args.debug_level,
        debug_dir=Path(args.debug_dir) if args.debug_dir else None,
        sleep_level=args.sleep_level,
        dry_run=args.dry_run,
        max_clip_count=args.max_clip_count,
    )
    errors = 0
    try:
        for account in accounts:
            try:
                sc.clip_for_account(account)
            except Error:
                if not args.continue_on_error:
                    raise
                traceback.print_exc()
                errors += 1
        if errors:
            print(f"Error clipping coupons for {errors} account(s)")
            sys.exit(1)
    except Exception as e:
        if args.debug_level:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
