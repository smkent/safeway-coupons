from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from safeway_coupons import SafewayCoupons
from safeway_coupons.errors import TooManyClipErrors
from safeway_coupons.models.safeway import Offer, OfferMap

from .utils import ClipsTestConfig, create_account, create_offer

if TYPE_CHECKING:
    from unittest import mock


@pytest.mark.usefixtures("http_responses")
@pytest.mark.usefixtures("login_success")
def test_safeway_coupons(
    available_offers: OfferMap, clips: ClipsTestConfig
) -> None:
    available_offers.offers |= {"1138": create_offer("1138")}
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=1)
    app.accounts = [create_account()]
    app()
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert not clips.failed_offer_ids


@pytest.mark.usefixtures("http_responses")
@pytest.mark.usefixtures("login_success")
def test_safeway_coupons_few_clip_errors(
    available_offers: OfferMap, clips: ClipsTestConfig
) -> None:
    available_offers.offers |= {str(i): create_offer(str(i)) for i in range(5)}
    clips.fail_response_offer_ids.add("1")
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=5)
    app.accounts = [create_account()]
    app()
    assert set(clips.clipped_offer_ids) == {"0", "2", "3", "4"}
    assert set(clips.failed_offer_ids) == {"1"}


@pytest.mark.usefixtures("http_responses")
@pytest.mark.usefixtures("login_success")
@pytest.mark.parametrize(
    "clip_fail_type", ["fail_http_offer_ids", "fail_response_offer_ids"]
)
def test_safeway_coupons_too_many_clip_errors(
    available_offers: OfferMap, clips: ClipsTestConfig, clip_fail_type: str
) -> None:
    available_offers.offers |= {str(i): create_offer(str(i)) for i in range(5)}
    for i in range(1, 4):
        getattr(clips, clip_fail_type).add(str(i))
    app = SafewayCoupons(
        send_email=False, debug_level=1, sleep_level=2, max_clip_errors=2
    )
    app.accounts = [create_account()]
    with pytest.raises(TooManyClipErrors):
        app()
    assert set(clips.clipped_offer_ids) == {"0"}
    assert set(clips.failed_offer_ids) == {"1", "2"}


@pytest.mark.usefixtures("http_responses")
@pytest.mark.usefixtures("login_success")
def test_safeway_coupons_invalid_offer_type(
    available_offers: OfferMap, clips: ClipsTestConfig
) -> None:
    offer_with_unknown_type = Offer.model_validate(
        create_offer("2187").model_dump(mode="json") | {"offer_pgm": "XX"}
    )
    available_offers.offers |= {
        "1138": create_offer("1138"),
        offer_with_unknown_type.offer_id: offer_with_unknown_type,
    }
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=1)
    app.accounts = [create_account()]
    app()
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert clips.failed_offer_ids == []


@pytest.mark.usefixtures("http_responses")
@pytest.mark.usefixtures("login_success")
@pytest.mark.parametrize(
    ("sleep_level", "max_sleep"), [(0, 25.0), (1, 1.0), (2, 0.0)]
)
def test_safeway_coupons_sleep_time(
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
    app.accounts = [create_account()]
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
