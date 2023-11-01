import json
import random
from pathlib import Path
from typing import List, Optional

import requests

from .accounts import Account
from .errors import ClipError, HTTPError
from .methods import ClipRequest, ClipResponse
from .models import Offer, OfferList
from .session import BaseSession, LoginSession


class SafewayClient(BaseSession):
    def __init__(self, account: Account, debug_dir: Optional[Path]) -> None:
        self.session = LoginSession(account, debug_dir)
        self.requests.headers.update(
            {
                "Authorization": f"Bearer {self.session.access_token}",
                "X-SW" "Y_AP" "I_K" "EY": "em" "j" "ou",
                "X-SW" "Y_VERSION": "1.1",
                "X-SW" "Y-APPLICATION-TYPE": "web",
            }
        )

    def get_offers(self) -> List[Offer]:
        try:
            response = self.requests.get(
                "https://www.safeway.com/abs/pub/xapi"
                "/offers/companiongalleryoffer"
                f"?storeId={self.session.store_id}"
                f"&rand={random.randrange(100000, 999999)}"
            )
            response.raise_for_status()
            return OfferList.from_dict(response.json()).offers
        except requests.exceptions.HTTPError as e:
            raise HTTPError(e, response) from e

    def clip(self, offer: Offer) -> None:
        request = ClipRequest.from_offer(offer)
        response: Optional[requests.Response] = None
        try:
            response = self.requests.post(
                "https://www.safeway.com/abs/pub/web/j4u/api/offers/clip"
                f"?storeId={self.session.store_id}",
                data=json.dumps(request.to_dict(encode_json=True)),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            clip_response = ClipResponse.from_dict(response.json())
            if not clip_response.success:
                raise Exception(
                    f"Unsuccessful clip response for coupon {offer}"
                )
        except Exception as e:
            raise ClipError(e, response, offer) from e
