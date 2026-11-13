from __future__ import annotations

from pydantic import Field

from .models import Model, Offer, OfferType


class ClipRequestItem(Model):
    clip_type: str
    item_id: str
    item_type: OfferType


class ClipRequest(Model):
    items: list[ClipRequestItem]

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


class ClipResponseItem(Model):
    clip_type: str
    item_id: str
    item_type: OfferType
    status: int
    clip_id: str = Field(coerce_numbers_to_str=True)
    checked: bool


class ClipResponse(Model):
    items: list[ClipResponseItem]

    @property
    def success(self) -> bool:
        return bool(self.items) and all(i.status == 1 for i in self.items)
