from __future__ import annotations

from enum import StrEnum
from typing import Any, Self


class Brand(StrEnum):
    """An Albertsons store brand.

    Values are the respective brand's web site second level domain.
    """

    Acme = "acmemarkets", "Acme"
    Albertsons = "albertsons", "Albertsons"
    Andronicos = "andronicos", "Andronico's"
    Balduccis = "balduccis", "Balducci's"
    Carrs = "carrsqc", "Carrs"
    Haggen = "haggen", "Haggen"
    JewelOsco = "jewelosco", "Jewel-Osco"
    Kings = "kingsfoodmarkets", "Kings"
    Pavilions = "pavilions", "Pavilions"
    Randalls = "randalls", "Randalls"
    Safeway = "safeway", "Safeway"
    Shaws = "shaws", "Shaw's"
    AlbertsonsMarket = "shopalbertsonsmarket", "Albertsons Market"
    Amigos = "shopamigos", "Amigos"
    MarketStreet = "shopmarketstreet", "Market Street"
    UnitedSupermarkets = "shopunitedsupermarkets", "United Supermarkets"
    StarMarket = "starmarket", "Star Market"
    TomThumb = "tomthumb", "Tom Thumb"
    Vons = "vons", "Vons"

    def __new__(cls, value: str, *_: Any, **__: Any) -> Self:
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    def __init__(self, _value: str, display_name: str = "") -> None:
        self.display_name = display_name

    @classmethod
    def _missing_(cls, value: object) -> Self:
        matches = [
            enum
            for enum in cls
            if str(value).lower().removesuffix(".com")
            in (v.lower() for v in (enum.name, enum.value, enum.display_name))
        ]
        if len(matches) == 1:
            return matches[0]
        raise ValueError(
            f"{value!r} is not a valid brand, use one of: "
            + ", ".join(repr(b.value) for b in cls)
        )

    @property
    def host(self) -> str:
        return f"www.{self.value}.com"

    @property
    def origin(self) -> str:
        return f"https://{self.host}"
