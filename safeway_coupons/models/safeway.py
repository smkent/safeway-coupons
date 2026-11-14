from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
)
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="ignore"
    )


def datetime_encode(dt: datetime) -> str:
    return str(int(datetime.timestamp(dt)) * 1000)


def datetime_decode(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromtimestamp(int(value) / 1000, UTC)


MillisDateTime = Annotated[
    datetime,
    BeforeValidator(datetime_decode),
    PlainSerializer(datetime_encode),
]


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


class OfferMap(Model):
    offers: dict[str, Offer] = Field(alias="companionGalleryOffer")


class OfferStatus(Enum):
    Clipped = "C"
    Unclipped = "U"
    Unknown = "?"

    @classmethod
    def _missing_(cls, value: object) -> OfferStatus:  # noqa: ARG003
        return cls(cls.Unknown)


class OfferType(Enum):
    StoreCoupon = "SC"
    ManufacturerCoupon = "MF"
    PersonalizedDeal = "PD"


class Offer(Model):
    offer_id: str
    status: OfferStatus
    name: str
    description: str
    start_date: MillisDateTime
    end_date: MillisDateTime
    offer_price: str
    offer_pgm: OfferType | str = Field(union_mode="left_to_right")
    category_type: str
    image: str
    category: str | None = None

    @property
    def offer_type(self) -> str:
        if isinstance(self.offer_pgm, str):
            return self.offer_pgm
        return self.offer_pgm.value

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__} "
            f"{self.offer_type} {self.offer_id}: "
            f"[{self.offer_price}] {self.name}"
        )
