import argparse

from .client import SafewayClient
from .config import Config
from .models import OfferStatus


def parse_args() -> argparse.Namespace:
    description = "Automatically add online coupons to your Safeway card"
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
        dest="email",
        action="store_false",
        help=(
            "Print summary information on standard output "
            "instead of sending email"
        ),
    )
    arg_parser.add_argument(
        "-S",
        "--no-sleep",
        dest="sleep_skip",
        action="count",
        default=0,
        help=(
            "Don't sleep between long requests. Specify twice to never sleep."
        ),
    )
    return arg_parser.parse_args()


def v2() -> None:
    args = parse_args()
    accounts = Config.load_accounts(config_file=args.accounts_config)
    for account in accounts:
        print(account)
        api = SafewayClient(account)
        offers = api.get_offers()
        i = 0
        for offer in offers:
            if offer.status == OfferStatus.Clipped:
                print(f"Already clipped {offer}")
                continue
            print(offer)
            # api.clip(offer)
            break
            i += 1
            if i >= 5:
                break
