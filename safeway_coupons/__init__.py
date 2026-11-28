"""Automatic coupon clipper for Safeway and other Albertsons brands' online "for U" coupons."""  # noqa: E501

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as import_version

from .account import Account
from .app import SafewayCoupons

try:
    version = import_version("safeway-coupons")
except PackageNotFoundError:  # pragma: no cover
    version = "0.0.0"

__all__ = ["Account", "SafewayCoupons", "version"]
