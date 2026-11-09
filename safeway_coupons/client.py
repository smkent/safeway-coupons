from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING

import requests

from .errors import ClipError, HTTPError
from .methods import ClipRequest, ClipResponse
from .models import Offer, OfferList
from .session import BaseSession, LoginSession

if TYPE_CHECKING:
    from pathlib import Path

    from .accounts import Account


class ClipResponseError(Exception):
    pass


class SafewayClient(BaseSession):
    def __init__(self, account: Account, debug_dir: Path | None) -> None:
        self.session = LoginSession(account, debug_dir)
        self.session_requests.headers.update(
            {
                "Authorization": f"Bearer {self.session.access_token}",
                "X-SWY_API_KEY": "emjou",
                "X-SWY_VERSION": "1.1",
                "X-SWY-APPLICATION-TYPE": "web",
            }
        )

    def get_offers(self) -> list[Offer]:
        try:
            response = self.session_requests.get(
                "https://www.safeway.com/abs/pub/xapi"
                "/offers/companiongalleryoffer"
                f"?storeId={self.session.store_id}"
                f"&rand={random.randrange(100000, 999999)}"  # noqa: S311
            )
            response.raise_for_status()
            return OfferList.from_dict(response.json()).offers
        except requests.exceptions.HTTPError as e:
            raise HTTPError(e, response) from e

    def clip(self, offer: Offer) -> None:
        request = ClipRequest.from_offer(offer)
        response: requests.Response | None = None
        try:
            response = self.session_requests.post(
                "https://www.safeway.com/abs/pub/web/j4u/api/offers/clip"
                f"?storeId={self.session.store_id}",
                data=json.dumps(request.to_dict(encode_json=True)),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            clip_response = ClipResponse.from_dict(response.json())
        except Exception as e:
            raise ClipError(e, response, offer) from e
        if not clip_response.success:
            raise ClipError(
                ClipResponseError(
                    f"Unsuccessful clip response for coupon {offer}"
                ),
                response,
                offer,
            )
