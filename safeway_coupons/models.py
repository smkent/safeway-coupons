from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import dataclasses_json


def datetime_encode(dt: datetime) -> str:
    return str(int(datetime.timestamp(dt)) * 1000)


def datetime_decode(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value) / 1000, UTC)


class Model(dataclasses_json.DataClassJsonMixin):
    dataclass_json_config = dataclasses_json.config(
        letter_case=dataclasses_json.LetterCase.CAMEL,
        undefined=dataclasses_json.Undefined.EXCLUDE,
        exclude=lambda f: f is None,
    )["dataclasses_json"]


@dataclass
class OfferMap(Model):
    offers: dict[str, Offer] = field(
        metadata=dataclasses_json.config(field_name="companionGalleryOffer")
    )


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
    Unknown = "?"

    @classmethod
    def _missing_(cls, value: object) -> OfferType:  # noqa: ARG003
        return cls(cls.Unknown)


@dataclass
class Offer(Model):
    offer_id: str
    status: OfferStatus
    name: str
    description: str
    start_date: datetime = field(
        metadata=dataclasses_json.config(
            encoder=datetime_encode, decoder=datetime_decode
        )
    )
    end_date: datetime = field(
        metadata=dataclasses_json.config(
            encoder=datetime_encode, decoder=datetime_decode
        )
    )
    offer_price: str
    offer_pgm: OfferType
    category_type: str
    image: str
    category: str | None = None

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__} "
            f"{self.offer_pgm.value} {self.offer_id}: "
            f"[{self.offer_price}] {self.name}"
        )
