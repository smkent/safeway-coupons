from .api_client import SafewayClient
from .config import Config
from .models import OfferStatus


def v2() -> None:
    accounts = Config.load_accounts()
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
