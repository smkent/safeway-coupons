from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from safeway_coupons.models.safeway import Offer, OfferStatus, OfferType


@dataclass
class ClipsTestConfig:
    fail_http_offer_ids: set[str] = field(default_factory=set)
    fail_response_offer_ids: set[str] = field(default_factory=set)
    clipped_offer_ids: list[str] = field(default_factory=list)
    failed_offer_ids: list[str] = field(default_factory=list)


def create_offer(offer_id: str) -> Offer:
    return Offer(
        offer_id=offer_id,
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
