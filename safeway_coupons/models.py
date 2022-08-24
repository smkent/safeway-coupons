from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import dataclasses_json


class Model(dataclasses_json.DataClassJsonMixin):
    dataclass_json_config = dataclasses_json.config(
        letter_case=dataclasses_json.LetterCase.CAMEL,  # type: ignore
        undefined=dataclasses_json.Undefined.EXCLUDE,
        exclude=lambda f: f is None,  # type: ignore
    )["dataclasses_json"]


@dataclass
class OfferList(Model):
    offers: List[Offer] = field(
        metadata=dataclasses_json.config(
            field_name="companionGalleryOfferList"
        )
    )


class OfferStatus(Enum):
    Clipped = "C"
    Unclipped = "U"
    Unknown = "?"

    @classmethod
    def _missing_(cls, value: object) -> OfferStatus:
        return cls(cls.Unknown)


@dataclass
class Offer(Model):
    offer_id: str
    status: OfferStatus
    name: str
    description: str
    offer_price: str
    offer_pgm: str
    category_type: str
    image: str
    category: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"<{self.__class__.__name__} {self.offer_id} "
            f"[{self.offer_price}] {self.name}>"
        )
