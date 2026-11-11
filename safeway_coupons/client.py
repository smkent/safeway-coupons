from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import requests
import requests.adapters

from .errors import ClipError, HTTPError
from .methods import ClipRequest, ClipResponse
from .models import Offer, OfferMap
from .session import LoginSession

if TYPE_CHECKING:
    from .accounts import Account


class ClipResponseError(Exception):
    pass


@dataclass
class SafewayClient:
    account: Account
    headless: bool = field(default=True, kw_only=True)
    debug_level: int = field(default=0, kw_only=True)

    def __post_init__(self) -> None:
        self.session = LoginSession(
            self.account, headless=self.headless, debug_level=self.debug_level
        )
        self.session_requests.headers["Authorization"] = (
            f"Bearer {self.session.access_token}"
        )

    @property
    def session_requests(self) -> requests.Session:
        if not hasattr(self, "_requests"):
            session = requests.Session()
            session.mount(
                "https://", requests.adapters.HTTPAdapter(pool_maxsize=1)
            )
            session.headers.update(
                {
                    "DNT": "1",
                    "User-Agent": self.session.user_agent,
                    "X-SWY_API_KEY": "emjou",
                    "X-SWY_VERSION": "1.1",
                    "X-SWY-APPLICATION-TYPE": "web",
                }
            )
            self._requests = session
        return self._requests

    def get_offers(self) -> OfferMap:
        try:
            response = self.session_requests.get(
                "https://www.safeway.com/abs/pub/xapi"
                "/offers/companiongalleryoffer"
                f"?storeId={self.session.store_id}"
                f"&rand={random.randrange(100000, 999999)}"  # noqa: S311
            )
            response.raise_for_status()
            return OfferMap.from_dict(response.json())
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
