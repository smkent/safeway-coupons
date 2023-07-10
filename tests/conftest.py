import json
import time
import urllib
from typing import Dict, Iterator, List, Mapping, Optional, Tuple, cast
from unittest import mock

import pytest
import pytest_mock
import requests
import responses
import undetected_chromedriver as uc  # type: ignore
from selenium.webdriver.support.wait import WebDriverWait

from safeway_coupons.models import Offer, OfferList

from .utils import ClipsTestConfig


@pytest.fixture
def http_responses() -> Iterator[responses.RequestsMock]:
    with responses.RequestsMock() as resp_mock:
        yield resp_mock


@pytest.fixture(autouse=True)
def mock_undetected_chromedriver(
    mock_web_driver_wait: mock.MagicMock,
    mock_sleep: mock.MagicMock,
) -> Iterator[mock.MagicMock]:
    with mock.patch.object(uc, "Chrome") as mock_uc:
        mock_driver = mock_uc.return_value.__enter__.return_value
        mock_uc.return_value.__exit__.side_effect = (
            lambda *a, **kw: mock_sleep.reset_mock()
        )
        yield mock_driver


@pytest.fixture(autouse=True)
def mock_web_driver_wait() -> Iterator[mock.MagicMock]:
    with mock.patch.object(WebDriverWait, "until") as mock_wdw:
        yield mock_wdw


@pytest.fixture
def login_success(mock_undetected_chromedriver: mock.MagicMock) -> None:
    cookies = {
        "SWY_SHARED_SESSION": {"accessToken": "test_token"},
        "SWY_SHARED_SESSION_INFO": {"info": {"J4U": {"storeId": 42}}},
    }

    def _get_cookie(name: str) -> Dict[str, Optional[str]]:
        value = cookies.get(name)
        return {
            "value": urllib.parse.quote(json.dumps(value)) if value else None
        }

    mock_undetected_chromedriver.get_cookie.side_effect = _get_cookie
    return


@pytest.fixture
def clips(
    http_responses: responses.RequestsMock,
) -> Iterator[ClipsTestConfig]:
    clips_test_config = ClipsTestConfig()

    def _clip_response(
        request: requests.PreparedRequest,
    ) -> Tuple[int, Mapping[str, str], str]:
        assert request.body
        data = json.loads(request.body)
        offer_id = data["items"][0]["itemId"]
        if offer_id in clips_test_config.fail_http_offer_ids:
            # This clip should return an HTTP error
            clips_test_config.failed_offer_ids.append(offer_id)
            return (400, {}, "")
        if offer_id in clips_test_config.fail_response_offer_ids:
            # This clip should return a non-successful response
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
) -> Iterator[List[Offer]]:
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


@pytest.fixture
def mock_sleep(mocker: pytest_mock.MockerFixture) -> Iterator[mock.MagicMock]:
    mocker.patch.object(time, "sleep")
    yield cast(mock.MagicMock, time.sleep)
