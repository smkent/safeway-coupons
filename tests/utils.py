from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Set

from safeway_coupons.accounts import Account
from safeway_coupons.models import Offer, OfferStatus, OfferType


@dataclass
class ClipsTestConfig:
    fail_http_offer_ids: Set[str] = field(default_factory=set)
    fail_response_offer_ids: Set[str] = field(default_factory=set)
    clipped_offer_ids: List[str] = field(default_factory=list)
    failed_offer_ids: List[str] = field(default_factory=list)


def create_offer(offer_id: str) -> Offer:
    return Offer(
        offer_id=offer_id,
        status=OfferStatus.Unclipped,
        name="Test Food",
        description="Test item for unit testing",
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        offer_price="$99 OFF",
        offer_pgm=OfferType.PersonalizedDeal,
        category_type="Unit Test foods",
        image="https://i.imgur.com/oWSZ8YM.jpg",
    )


def create_account() -> Account:
    return Account(
        username="ness@onett.example",
        password="pk_fire",
        mail_from="ness@onett.example",
        mail_to="ness@onett.example",
    )
