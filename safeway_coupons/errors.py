from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests

from .accounts import Account
from .models import Offer


@dataclass
class Error(Exception):
    exception: Exception


@dataclass
class AuthenticationFailure(Error):
    account: Account
    attachments: Optional[List[Path]] = None

    def __str__(self) -> str:
        return f"Authentication Failure ({self.exception})"


@dataclass
class HTTPError(Error):
    response: requests.Response

    def __str__(self) -> str:
        return str(self.exception)


@dataclass
class ClipError(Error):
    response: Optional[requests.Response]
    offer: Offer

    def __str__(self) -> str:
        return f"Clip Error for {self.offer} ({self.exception})"


@dataclass
class TooManyClipErrors(Error):
    clipped_offers: List[Offer]
    errors: List[ClipError]

    def __str__(self) -> str:
        return (
            f"Exited after {len(self.errors)} clip errors "
            f"(Last: {self.exception})"
        )
