from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from safeway_coupons import SafewayCoupons
from safeway_coupons.errors import TooManyClipErrors
from safeway_coupons.models.safeway.offers import Offer, OfferMap

from .utils import ClipsTestConfig, create_offer

if TYPE_CHECKING:
    from pathlib import Path

    import responses

    from safeway_coupons.account import Account

    from .conftest import MainRunner


@pytest.mark.usefixtures("http_responses")
def test_safeway_coupons(
    account: Account, available_offers: OfferMap, clips: ClipsTestConfig
) -> None:
    available_offers.offers |= {"1138": create_offer("1138")}
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=1)
    app.accounts = [account]
    app()
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert not clips.failed_offer_ids


@pytest.mark.usefixtures("http_responses")
def test_safeway_coupons_few_clip_errors(
    account: Account, available_offers: OfferMap, clips: ClipsTestConfig
) -> None:
    available_offers.offers |= {str(i): create_offer(str(i)) for i in range(5)}
    clips.fail_response_offer_ids.add("1")
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=5)
    app.accounts = [account]
    app()
    assert set(clips.clipped_offer_ids) == {"0", "2", "3", "4"}
    assert set(clips.failed_offer_ids) == {"1"}


@pytest.mark.usefixtures("http_responses")
@pytest.mark.parametrize(
    "clip_fail_type", ["fail_http_offer_ids", "fail_response_offer_ids"]
)
def test_safeway_coupons_too_many_clip_errors(
    account: Account,
    available_offers: OfferMap,
    clips: ClipsTestConfig,
    clip_fail_type: str,
) -> None:
    available_offers.offers |= {str(i): create_offer(str(i)) for i in range(5)}
    for i in range(1, 4):
        getattr(clips, clip_fail_type).add(str(i))
    app = SafewayCoupons(
        send_email=False, debug_level=1, sleep_level=2, max_clip_errors=2
    )
    app.accounts = [account]
    with pytest.raises(TooManyClipErrors):
        app()
    assert set(clips.clipped_offer_ids) == {"0"}
    assert set(clips.failed_offer_ids) == {"1", "2"}


@pytest.mark.usefixtures("http_responses")
def test_safeway_coupons_invalid_offer_type(
    account: Account, available_offers: OfferMap, clips: ClipsTestConfig
) -> None:
    offer_with_unknown_type = Offer.model_validate(
        create_offer("2187").model_dump(mode="json") | {"offer_pgm": "XX"}
    )
    available_offers.offers |= {
        "1138": create_offer("1138"),
        offer_with_unknown_type.offer_id: offer_with_unknown_type,
    }
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=1)
    app.accounts = [account]
    app()
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert clips.failed_offer_ids == []


@pytest.mark.usefixtures("http_responses")
@pytest.mark.parametrize(
    ("sleep_level", "max_sleep"), [(0, 25.0), (1, 1.0), (2, 0.0)]
)
def test_safeway_coupons_sleep_time(
    account: Account,
    available_offers: OfferMap,
    clips: ClipsTestConfig,
    mock_sleep: mock.MagicMock,
    sleep_level: int,
    max_sleep: float,
) -> None:
    offers_count = 100
    available_offers.offers |= {
        str(i): create_offer(str(i)) for i in range(offers_count)
    }
    app = SafewayCoupons(
        send_email=False, sleep_level=sleep_level, max_clip_errors=1
    )
    app.accounts = [account]
    app()
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
def mail_log(tmp_path: Path) -> Path:
    return tmp_path / "mail.log"


@pytest.fixture
def sendmail(tmp_path: Path, mail_log: Path) -> Path:
    script = tmp_path / "sendmail"
    script.write_text(f'#!/bin/sh\ncat >> "{mail_log}"\n')
    script.chmod(0o755)
    return script


@pytest.fixture
def two_accounts_config(tmp_path: Path) -> Path:
    config = tmp_path / "two_accounts"
    config.write_text(
        os.linesep.join(
            (
                "[ness@onett.example]",
                "password = pk_fire",
                "",
                "[paula@twoson.example]",
                "password = pk_fire",
            )
        )
    )
    return config


def test_dry_run_signs_in(
    main_runner: MainRunner,
    accounts_config: Path,
    sendmail: Path,
    mail_log: Path,
    available_offers: OfferMap,
    http_responses: responses.RequestsMock,
    mock_browser_driver: mock.MagicMock,
) -> None:
    available_offers.offers |= {"1138": create_offer("1138")}
    main_runner("-c", str(accounts_config), "--sendmail", str(sendmail), "-p")
    browser = mock_browser_driver.return_value.__enter__.return_value
    browser.sign_in.assert_called_once_with(check=False)
    assert [c.request.method for c in http_responses.calls] == ["GET"]
    assert not mail_log.exists()


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
    sendmail: Path,
    mail_log: Path,
    mock_browser_driver: mock.MagicMock,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    status: str,
    *,
    check: bool,
) -> None:
    main_runner(
        "-c",
        str(two_accounts_config),
        "--sendmail",
        str(sendmail),
        "--login-only",
        *argv,
    )
    browser = mock_browser_driver.return_value.__enter__.return_value
    assert browser.sign_in.call_args_list == [mock.call(check=check)] * 2
    out, err = capsys.readouterr()
    for username in ("ness@onett.example", "paula@twoson.example"):
        assert f"{status} for Safeway account {username}" in out
    assert not err
    assert not mail_log.exists()
