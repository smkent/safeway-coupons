from typing import List

import pytest
import responses

from safeway_coupons import Account, SafewayCoupons
from safeway_coupons.models import Offer

from .utils import ClipsTestConfig, create_offer


@pytest.mark.usefixtures("login_success")
def test_safeway_coupons(
    http_responses: responses.RequestsMock,
    available_offers: List[Offer],
    clips: ClipsTestConfig,
) -> None:
    available_offers.append(create_offer("1138"))
    app = SafewayCoupons(send_email=False, sleep_level=2, max_clip_errors=1)
    app.clip_for_account(
        Account(
            username="ness@onett.example",
            password="pk_fire",
            mail_from="ness@onett.example",
            mail_to="ness@onett.example",
        )
    )
    assert set(clips.clipped_offer_ids) == {"1138"}
    assert not clips.failed_offer_ids
