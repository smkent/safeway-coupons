import os

from .api_client import SafewayClient
from .models import OfferStatus


def v2() -> None:
    user = os.environ["USER"]
    password = os.environ["PASS"]
    api = SafewayClient(user, password)
    offers = api.get_offers()
    i = 0
    for offer in offers:
        if offer.status == OfferStatus.Clipped:
            print(f"Already clipped {offer}")
            continue
        print(offer)
        api.clip(offer)
        break
        i += 1
        if i >= 5:
            break
