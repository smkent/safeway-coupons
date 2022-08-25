from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import Model, Offer, OfferType


@dataclass
class ClipRequestItem(Model):
    clip_type: str
    item_id: str
    item_type: OfferType


@dataclass
class ClipRequest(Model):
    items: List[ClipRequestItem]

    @classmethod
    def from_offer(cls, offer: Offer) -> ClipRequest:
        return cls(
            items=[
                ClipRequestItem(
                    clip_type=clip_type,
                    item_id=offer.offer_id,
                    item_type=offer.offer_pgm,
                )
                for clip_type in ["C", "L"]
            ]
        )


@dataclass
class ClipResponseItem(Model):
    clip_type: str
    item_id: str
    item_type: OfferType
    status: int
    clip_id: str
    checked: bool


@dataclass
class ClipResponse(Model):
    items: List[ClipResponseItem]

    @property
    def success(self) -> bool:
        return bool(self.items) and all(i.status == 1 for i in self.items)
