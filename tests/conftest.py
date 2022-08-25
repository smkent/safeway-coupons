import json
from typing import Iterable, List, Mapping, Tuple

import pytest
import requests
import responses

from safeway_coupons.models import Offer, OfferList

from .utils import ClipsTestConfig


@pytest.fixture
def http_responses() -> Iterable[responses.RequestsMock]:
    with responses.RequestsMock() as resp_mock:
        yield resp_mock


@pytest.fixture
def login_success(http_responses: responses.RequestsMock) -> None:
    http_responses.add(
        method=responses.POST,
        url="https://albertsons.okta.com/api/v1/authn",
        body=json.dumps({"status": "SUCCESS", "sessionToken": "test"}),
    )
    session_data = {"accessToken": "test_token"}
    session_info = {"info": {"J4U": {"storeId": 42}}}
    http_responses.add(
        method=responses.GET,
        url=(
            "https://albertsons.okta.com"
            "/oauth2/ausp6soxrIyPrm8rS2p6/v1/authorize"
        ),
        headers={
            "Set-Cookie": f"SWY_SHARED_SESSION={json.dumps(session_data)} ",
            "set-cookie": (
                f"SWY_SHARED_SESSION_INFO={json.dumps(session_info)}"
            ),
        },
    )


@pytest.fixture
def clips(
    http_responses: responses.RequestsMock,
) -> Iterable[ClipsTestConfig]:
    clips_test_config = ClipsTestConfig()

    def _clip_response(
        request: requests.PreparedRequest,
    ) -> Tuple[int, Mapping[str, str], str]:
        assert request.body
        data = json.loads(request.body)
        offer_id = data["items"][0]["itemId"]
        if offer_id in clips_test_config.fail_offer_ids:
            # This clip should fail
            clip_status = 0
            clips_test_config.failed_offer_ids.append(offer_id)
        else:
            # This clip should succeed
            clip_status = 1
            clips_test_config.clipped_offer_ids.append(offer_id)
        for clip_item in data["items"]:
            clip_item.update(
                {"status": clip_status, "clipId": 1000, "checked": False}
            )

        return (200, {"Content-Type": "application/json"}, json.dumps(data))

    http_responses.add_callback(
        method=responses.POST,
        url=("https://www.safeway.com/abs/pub/web/j4u/api/offers/clip"),
        callback=_clip_response,
    )
    yield clips_test_config


@pytest.fixture
def available_offers(
    http_responses: responses.RequestsMock,
) -> Iterable[List[Offer]]:
    offers_list: List[Offer] = []
    http_responses.add_callback(
        method=responses.GET,
        url=(
            "https://www.safeway.com/abs/pub/xapi/offers/companiongalleryoffer"
        ),
        callback=lambda request: (
            200,
            {"Content-Type": "application/json"},
            json.dumps(
                OfferList(offers=offers_list).to_dict(encode_json=True)
            ),
        ),
    )
    yield offers_list
