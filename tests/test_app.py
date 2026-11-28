from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
import responses

from safeway_coupons import SafewayCoupons
from safeway_coupons.account import AccountsFile
from safeway_coupons.models.fields import Password
from safeway_coupons.models.safeway.offers import (
    Offer,
    OfferMap,
    OfferStatus,
    OfferType,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path
    from unittest.mock import MagicMock

    import requests

    from .utils import CapLogHelper, MainRunner, MockMail


@dataclass
class ClipsTestConfig:
    fail_http_offer_ids: set[str] = field(default_factory=set)
    fail_response_offer_ids: set[str] = field(default_factory=set)
    clipped_offer_ids: list[str] = field(default_factory=list)
    failed_offer_ids: list[str] = field(default_factory=list)


create_offer = partial(
    Offer,
    status=OfferStatus.Unclipped,
    name="Test Food",
    description="Test item for unit testing",
    start_date=datetime.now(tz=UTC) - timedelta(days=1),
    end_date=datetime.now(tz=UTC) + timedelta(days=1),
    offer_price="$99 OFF",
    offer_pgm=OfferType.PersonalizedDeal,
    category_type="Unit Test foods",
    image="https://i.imgur.com/oWSZ8YM.jpg",
)


@pytest.fixture(autouse=True)
def mock_sleep() -> Iterator[MagicMock]:
    with patch.object(time, "sleep") as obj:
        yield obj


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


@pytest.mark.usefixtures("http_responses")
def test_safeway_coupons(
    main_runner: MainRunner,
    accounts_config: Path,
    available_offers: OfferMap,
    clips: ClipsTestConfig,
) -> None:
    available_offers.offers |= {"1138": create_offer(offer_id="1138")}
    main_runner(
        "-c",
        str(accounts_config),
        "--no-notify",
        "--no-sleep",
        "--no-sleep",
    )
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert not clips.failed_offer_ids


@pytest.mark.usefixtures("http_responses")
def test_safeway_coupons_few_clip_errors(
    main_runner: MainRunner,
    accounts_config: Path,
    available_offers: OfferMap,
    clips: ClipsTestConfig,
) -> None:
    available_offers.offers |= {
        str(i): create_offer(offer_id=str(i)) for i in range(5)
    }
    clips.fail_response_offer_ids.add("1")
    main_runner(
        "-c", str(accounts_config), "--no-notify", "--no-sleep", "--no-sleep"
    )
    assert set(clips.clipped_offer_ids) == {"0", "2", "3", "4"}
    assert set(clips.failed_offer_ids) == {"1"}


@pytest.mark.usefixtures("http_responses")
@pytest.mark.parametrize(
    "clip_fail_type", ["fail_http_offer_ids", "fail_response_offer_ids"]
)
def test_safeway_coupons_too_many_clip_errors(
    caplog_helper: CapLogHelper,
    main_runner: MainRunner,
    accounts_config: Path,
    available_offers: OfferMap,
    clips: ClipsTestConfig,
    clip_fail_type: str,
) -> None:
    available_offers.offers |= {
        str(i): create_offer(offer_id=str(i)) for i in range(5)
    }
    for i in range(1, 4):
        getattr(clips, clip_fail_type).add(str(i))
    with patch.object(
        SafewayCoupons, "max_clip_errors", PropertyMock(return_value=2)
    ):
        main_runner(
            "-c",
            str(accounts_config),
            "--no-notify",
            "--no-sleep",
            "--no-sleep",
            match=1,
        )
    assert set(clips.clipped_offer_ids) == {"0"}
    assert set(clips.failed_offer_ids) == {"1", "2"}
    assert (
        len(
            caplog_helper.match_records(
                "Error for account ness@onett.example:"
                " Exited after 2 clip errors (Last: "
            )
        )
        == 1
    )


@pytest.mark.usefixtures("http_responses")
def test_safeway_coupons_invalid_offer_type(
    main_runner: MainRunner,
    accounts_config: Path,
    available_offers: OfferMap,
    clips: ClipsTestConfig,
) -> None:
    offer_with_unknown_type = Offer.model_validate(
        create_offer(offer_id="2187").model_dump(mode="json")
        | {"offer_pgm": "XX"}
    )
    available_offers.offers |= {
        "1138": create_offer(offer_id="1138"),
        offer_with_unknown_type.offer_id: offer_with_unknown_type,
    }
    main_runner(
        "-c", str(accounts_config), "--no-notify", "--no-sleep", "--no-sleep"
    )
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert clips.failed_offer_ids == []


@pytest.mark.usefixtures("http_responses")
@pytest.mark.parametrize(
    ("sleep_level", "max_sleep"), [(0, 25.0), (1, 1.0), (2, 0.0)]
)
def test_safeway_coupons_sleep_time(
    main_runner: MainRunner,
    accounts_config: Path,
    available_offers: OfferMap,
    clips: ClipsTestConfig,
    mock_sleep: MagicMock,
    sleep_level: int,
    max_sleep: float,
) -> None:
    offers_count = 100
    available_offers.offers |= {
        str(i): create_offer(offer_id=str(i)) for i in range(offers_count)
    }
    main_runner(
        "-c",
        str(accounts_config),
        "--no-notify",
        *(["--no-sleep"] * sleep_level),
    )
    if max_sleep:
        assert mock_sleep.call_count == offers_count
        assert max(i.args[0] for i in mock_sleep.call_args_list) <= max_sleep
    else:
        mock_sleep.assert_not_called()
    assert set(clips.clipped_offer_ids) == {
        str(i) for i in range(offers_count)
    }
    assert not clips.failed_offer_ids


@pytest.fixture
def two_accounts_config() -> Path:
    config = AccountsFile.default_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        os.linesep.join(
            (
                "[accounts.ness]",
                'username = "ness@onett.example"',
                f'password = "{Password.encode("pk_fire")}"',
                "",
                "[accounts.paula]",
                'username = "paula@twoson.example"',
                f'password = "{Password.encode("pk_fire")}"',
            )
        )
    )
    return config


def test_dry_run_signs_in(
    main_runner: MainRunner,
    accounts_config: Path,
    mail: MockMail,
    available_offers: OfferMap,
    http_responses: responses.RequestsMock,
    mock_browser_driver: MagicMock,
) -> None:
    available_offers.offers |= {"1138": create_offer(offer_id="1138")}
    main_runner("-p")
    mock_browser_driver.sign_in.assert_called_once_with(check=False)
    assert [c.request.method for c in http_responses.calls] == ["GET"]
    assert not mail.messages


@pytest.mark.usefixtures("http_responses")
@pytest.mark.parametrize(
    ("argv", "check", "status"),
    [
        pytest.param([], False, "Signing in", id="live"),
        pytest.param(["-p"], True, "Checking sign in", id="dry_run"),
    ],
)
def test_login_only(
    main_runner: MainRunner,
    two_accounts_config: Path,
    mail: MockMail,
    mock_browser_driver: MagicMock,
    caplog: pytest.LogCaptureFixture,
    argv: list[str],
    status: str,
    *,
    check: bool,
) -> None:
    main_runner("--login-only", *argv)
    assert (
        mock_browser_driver.sign_in.call_args_list == [call(check=check)] * 2
    )
    for username in ("ness@onett.example", "paula@twoson.example"):
        assert f"{status} for Safeway account {username}" in caplog.messages
    assert not mail.messages
