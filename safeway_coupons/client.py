import json
import random
from typing import List

from .account import Account
from .errors import ClipError
from .methods import ClipRequest, ClipResponse
from .models import Offer, OfferList
from .session import BaseSession, LoginSession


class SafewayClient(BaseSession):
    def __init__(self, account: Account) -> None:
        self.session = LoginSession(account)
        self.requests.headers.update(
            {
                "Authorization": f"Bearer {self.session.access_token}",
                "X-SW" "Y_AP" "I_K" "EY": "em" "j" "ou",
                "X-SW" "Y_VERSION": "1.1",
                "X-SW" "Y-APPLICATION-TYPE": "web",
            }
        )

    def get_offers(self) -> List[Offer]:
        response = self.requests.get(
            "https://www.safeway.com/abs/pub/xapi"
            "/offers/companiongalleryoffer"
            f"?storeId={self.session.store_id}"
            f"&rand={random.randrange(100000,999999)}",
        )
        response.raise_for_status()
        return OfferList.from_dict(response.json()).offers

    def clip(self, offer: Offer) -> None:
        try:
            request = ClipRequest.from_offer(offer)
            response = self.requests.post(
                "https://www.safeway.com/abs/pub/web/j4u/api/offers/clip"
                f"?storeId={self.session.store_id}",
                data=json.dumps(request.to_dict(encode_json=True)),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            clip_response = ClipResponse.from_dict(response.json())
            if not clip_response.success:
                raise Exception(f"Error clipping coupon {offer}")
        except Exception as e:
            raise ClipError(offer) from e
