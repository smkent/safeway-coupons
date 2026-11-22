from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import responses

from safeway_coupons.account import Account
from safeway_coupons.client.browser import SafewayBrowserSession
from safeway_coupons.console import console
from safeway_coupons.dirs import dirs
from safeway_coupons.models.safeway.offers import OfferMap

from .utils import CapLogHelper, ClipsTestConfig, MainRunner, MockMail

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    import requests


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "browser: Playwright browser based tests with a mock site"
    )


@pytest.fixture
def main_runner(monkeypatch: pytest.MonkeyPatch) -> MainRunner:
    return MainRunner(monkeypatch=monkeypatch)


@pytest.fixture(autouse=True)
def console_reset() -> None:
    console.configure()


@pytest.fixture(autouse=True)
def mock_config_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dirs, "state", tmp_path / "state")


@pytest.fixture(autouse=True)
def mail() -> Iterator[MockMail]:
    with MockMail() as mock_mail:
        yield mock_mail


@pytest.fixture
def caplog_helper(caplog: pytest.LogCaptureFixture) -> CapLogHelper:
    return CapLogHelper(caplog=caplog)


@pytest.fixture
def mock_sleep() -> Iterator[MagicMock]:
    with patch.object(time, "sleep") as obj:
        yield obj


@pytest.fixture
def http_responses() -> Iterator[responses.RequestsMock]:
    with responses.RequestsMock() as resp_mock:
        yield resp_mock


@pytest.fixture
def mock_browser_driver_enter() -> Iterator[MagicMock]:
    with patch.object(
        SafewayBrowserSession, "__enter__", autospec=True
    ) as obj:
        yield obj


@pytest.fixture(autouse=True)
def mock_browser_driver(
    mock_browser_driver_enter: MagicMock, mock_sleep: MagicMock
) -> MagicMock:
    instance = create_autospec(SafewayBrowserSession, instance=True)
    instance.user_agent = "UnitTestUserAgent/1.0"

    def _enter(self: SafewayBrowserSession) -> MagicMock:
        instance.account = self.account
        return instance

    mock_browser_driver_enter.side_effect = _enter
    return instance


@pytest.fixture
def account() -> Account:
    return Account(
        username="ness@onett.example",
        password="pk_fire",  # noqa: S106
        mail_from="ness@onett.example",
        mail_to="ness@onett.example",
    )


@pytest.fixture
def accounts_config(tmp_path: Path) -> Path:
    accounts_file = tmp_path / "test_accounts"
    accounts_file.write_text(
        os.linesep.join(
            (
                "[_global]",
                "email_sender = ness@onett.example",
                "",
                "[ness@onett.example]",
                "password = pk_fire",
                "notify = ness@onett.example",
            )
        )
    )
    return accounts_file


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
