from __future__ import annotations

import json
import os
import sys
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import responses
import rich

from safeway_coupons.account import (
    Account,
    AccountsFile,
    EmailConfig,
    NotifyConfig,
)
from safeway_coupons.client.browser import SafewayBrowserSession
from safeway_coupons.console import console
from safeway_coupons.models.fields import Password
from safeway_coupons.models.safeway.offers import OfferMap

from .accounts import ACCOUNTS_TOML
from .utils import (
    CapLogHelper,
    ClipsTestConfig,
    MainRunner,
    MockDirs,
    MockMail,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    import requests


pytest.register_assert_rewrite("tests.cli.utils")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "browser: Playwright browser based tests with a mock site"
    )


@pytest.fixture(autouse=True)
def mock_stdin_isatty() -> Iterator[None]:
    with patch.object(sys.stdin, "isatty", return_value=False):
        yield


@pytest.fixture
def main_runner(monkeypatch: pytest.MonkeyPatch) -> MainRunner:
    return MainRunner(monkeypatch=monkeypatch)


@pytest.fixture(autouse=True)
def console_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr(rich, "_console", None)
    console.configure()


@pytest.fixture(params=[MockDirs.Type.param(MockDirs.Type.StorageDir)])
def mock_dirs_type(request: pytest.FixtureRequest) -> MockDirs.Type:
    return request.param


@pytest.fixture(autouse=True)
def mock_dirs(
    tmp_path: Path, *, mock_dirs_type: MockDirs.Type
) -> Iterator[MockDirs]:
    base_storage_dir = tmp_path / "storage"
    with MockDirs(
        base_storage_dir=base_storage_dir, type=mock_dirs_type
    ) as pd:
        yield pd


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
        name="ness",
        username="ness@onett.example",
        password=Password.encode("pk_fire"),
        notify=NotifyConfig(
            email=EmailConfig(
                to="ness@onett.example", mail_from="ness@onett.example"
            )
        ),
    )


@pytest.fixture
def accounts_toml() -> Path:
    accounts_file = AccountsFile.default_path()
    accounts_file.parent.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text(ACCOUNTS_TOML)
    accounts_file.chmod(0o600)
    return accounts_file


@pytest.fixture
def accounts_config() -> Path:
    accounts_file = AccountsFile.default_path()
    accounts_file.parent.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text(
        os.linesep.join(
            (
                "[accounts.ness]",
                'username = "ness@onett.example"',
                f'password = "{Password.encode("pk_fire")}"',
                "",
                "[accounts.ness.notify.email]",
                'to = "ness@onett.example"',
                'from = "ness@onett.example"',
            )
        )
    )
    accounts_file.chmod(0o600)
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
