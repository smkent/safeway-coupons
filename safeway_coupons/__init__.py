"""Automatic coupon clipper for Safeway's online "Safeway for U" coupons."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as import_version

from .accounts import Account
from .safeway import SafewayCoupons

try:
    version = import_version("safeway-coupons")
except PackageNotFoundError:  # pragma: no cover
    version = "0.0.0"

__all__ = ["version", "Account", "SafewayCoupons"]
