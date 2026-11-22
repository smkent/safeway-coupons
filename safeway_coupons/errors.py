from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import requests

    from .account import Account
    from .models.safeway.offers import Offer


@dataclass
class Error(Exception):
    attachments: list[Path] | None = field(default=None, kw_only=True)


@dataclass
class AccountLockedError(Error):
    account: Account

    def __str__(self) -> str:
        return f"Account {self.account.username} is in use by another process"


@dataclass
class AuthenticationFailure(Error):  # noqa: N818
    account: Account

    def __str__(self) -> str:
        return f"Authentication Failure ({self.__cause__})"


@dataclass
class MultiFactorAuthenticationRequired(AuthenticationFailure):
    def __str__(self) -> str:
        return (
            f"{self.account.username} needs an MFA verification code to"
            " sign in. Sign in with --login-only from a terminal."
        )


@dataclass
class NotSignedIn(AuthenticationFailure):
    def __str__(self) -> str:
        return f"Account {self.account.username} is not signed in"


@dataclass
class BrowserSessionError(Error):
    message: str | None = field(default=None, kw_only=True)

    def __str__(self) -> str:
        return self.message or str(self.__cause__ or "Browser session error")


@dataclass
class HTTPError(Error):
    response: requests.Response

    def __str__(self) -> str:
        return str(self.__cause__)


@dataclass
class ClipError(Error):
    offer: Offer
    message: str | None = field(default=None, kw_only=True)
    response: requests.Response | None = field(default=None, kw_only=True)

    def __str__(self) -> str:
        info = str(self.message or self.__cause__)
        return f"Clip error for {self.offer}" + (f" ({info})" if info else "")


@dataclass
class TooManyClipErrors(Error):  # noqa: N818
    clipped_offers: list[Offer]
    errors: list[ClipError]

    def __str__(self) -> str:
        return (
            f"Exited after {len(self.errors)} clip errors "
            f"(Last: {self.__cause__})"
        )
