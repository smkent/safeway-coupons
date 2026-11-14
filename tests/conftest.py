from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import responses

from safeway_coupons.__main__ import main
from safeway_coupons.client import session
from safeway_coupons.dirs import dirs
from safeway_coupons.models.safeway import OfferMap

from .utils import ClipsTestConfig

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path
    from unittest.mock import MagicMock

    import requests


@dataclass
class MainRunner:
    monkeypatch: pytest.MonkeyPatch

    def __call__(self, *cmd: str, match: int = 0) -> None:
        self.monkeypatch.setattr(sys, "argv", ["safeway-coupons", *cmd])
        with pytest.raises(SystemExit, match=str(match)):
            main()


@pytest.fixture
def main_runner(monkeypatch: pytest.MonkeyPatch) -> MainRunner:
    return MainRunner(monkeypatch=monkeypatch)


@pytest.fixture(autouse=True)
def mock_config_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dirs, "state", tmp_path / "state")


@pytest.fixture
def mock_sleep() -> Iterator[MagicMock]:
    with patch.object(time, "sleep") as obj:
        yield obj


@pytest.fixture
def http_responses() -> Iterator[responses.RequestsMock]:
    with responses.RequestsMock() as resp_mock:
        yield resp_mock


@pytest.fixture(autouse=True)
def mock_browser_driver(mock_sleep: MagicMock) -> Iterator[MagicMock]:
    with patch.object(session, "SafewayBrowserSession", autospec=True) as obj:
        instance = obj.return_value.__enter__.return_value
        instance.user_agent = "UnitTestUserAgent/1.0"
        yield obj


@pytest.fixture
def login_success(mock_browser_driver: MagicMock) -> None:
    cookies = {
        "SWY_SHARED_SESSION": {"accessToken": "test_token"},
        "SWY_SHARED_SESSION_INFO": {"info": {"J4U": {"storeId": 42}}},
    }

    mock_browser_driver.cookies = cookies
    return


@pytest.fixture
def clips(
    http_responses: responses.RequestsMock,
) -> ClipsTestConfig:
    clips_test_config = ClipsTestConfig()

    def _clip_response(
        request: requests.PreparedRequest,
    ) -> tuple[int, Mapping[str, str], str]:
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
    return clips_test_config


@pytest.fixture
def available_offers(http_responses: responses.RequestsMock) -> OfferMap:
    offer_map: OfferMap = OfferMap(offers={})
    http_responses.add_callback(
        method=responses.GET,
        url=(
            "https://www.safeway.com/abs/pub/xapi/offers/companiongalleryoffer"
        ),
        callback=lambda request: (
            200,
            {"Content-Type": "application/json"},
            json.dumps(
                offer_map.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
            ),
        ),
    )
    return offer_map
