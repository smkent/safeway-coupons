from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, Field, PlainSerializer

from .base import Model


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
