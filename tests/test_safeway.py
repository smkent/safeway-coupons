from typing import List
from unittest import mock

import pytest
import responses

from safeway_coupons import SafewayCoupons
from safeway_coupons.errors import TooManyClipErrors
from safeway_coupons.models import Offer

from .utils import ClipsTestConfig, create_account, create_offer


@pytest.mark.usefixtures("login_success")
def test_safeway_coupons(
    http_responses: responses.RequestsMock,
    available_offers: List[Offer],
    clips: ClipsTestConfig,
) -> None:
    available_offers.append(create_offer("1138"))
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=1)
    app.clip_for_account(create_account())
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert not clips.failed_offer_ids


@pytest.mark.usefixtures("login_success")
def test_safeway_coupons_few_clip_errors(
    http_responses: responses.RequestsMock,
    available_offers: List[Offer],
    clips: ClipsTestConfig,
) -> None:
    available_offers += [create_offer(str(i)) for i in range(5)]
    clips.fail_response_offer_ids.add("1")
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=5)
    app.clip_for_account(create_account())
    assert set(clips.clipped_offer_ids) == {"0", "2", "3", "4"}
    assert set(clips.failed_offer_ids) == {"1"}


@pytest.mark.usefixtures("login_success")
@pytest.mark.parametrize(
    "clip_fail_type", ["fail_http_offer_ids", "fail_response_offer_ids"]
)
def test_safeway_coupons_too_many_clip_errors(
    http_responses: responses.RequestsMock,
    available_offers: List[Offer],
    clips: ClipsTestConfig,
    clip_fail_type: str,
) -> None:
    available_offers += [create_offer(str(i)) for i in range(5)]
    for i in range(1, 4):
        getattr(clips, clip_fail_type).add(str(i))
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=2)
    with pytest.raises(TooManyClipErrors):
        app.clip_for_account(create_account())
    assert set(clips.clipped_offer_ids) == {"0"}
    assert set(clips.failed_offer_ids) == {"1", "2"}


@pytest.mark.usefixtures("login_success")
@pytest.mark.parametrize(
    ["sleep_level", "max_sleep"], [(0, 25.0), (1, 1.0), (2, 0.0)]
)
def test_safeway_coupons_sleep_time(
    http_responses: responses.RequestsMock,
    available_offers: List[Offer],
    clips: ClipsTestConfig,
    mock_sleep: mock.MagicMock,
    sleep_level: int,
    max_sleep: float,
) -> None:
    offers_count = 100
    available_offers += [create_offer(str(i)) for i in range(offers_count)]
    app = SafewayCoupons(
        send_email=False, sleep_level=sleep_level, max_clip_errors=1
    )
    app.clip_for_account(create_account())
    if max_sleep:
        assert mock_sleep.call_count == offers_count
        assert max(i.args[0] for i in mock_sleep.call_args_list) <= max_sleep
    else:
        mock_sleep.assert_not_called()
    assert set(clips.clipped_offer_ids) == {
        str(i) for i in range(offers_count)
    }
    assert not clips.failed_offer_ids
