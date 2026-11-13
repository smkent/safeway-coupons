from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import requests

    from .account import Account
    from .models.safeway import Offer


@dataclass
class Error(Exception):
    exception: Exception


@dataclass
class AccountLockedError(Error):
    account: Account

    def __str__(self) -> str:
        return f"Account {self.account.username} is in use by another process"


@dataclass
class AuthenticationFailure(Error):  # noqa: N818
    account: Account
    attachments: list[Path] | None = None

    def __str__(self) -> str:
        return f"Authentication Failure ({self.exception})"


@dataclass
class HTTPError(Error):
    response: requests.Response

    def __str__(self) -> str:
        return str(self.exception)


@dataclass
class ClipError(Error):
    response: requests.Response | None
    offer: Offer

    def __str__(self) -> str:
        return f"Clip Error for {self.offer} ({self.exception})"


@dataclass
class TooManyClipErrors(Error):  # noqa: N818
    clipped_offers: list[Offer]
    errors: list[ClipError]

    def __str__(self) -> str:
        return (
            f"Exited after {len(self.errors)} clip errors "
            f"(Last: {self.exception})"
        )
