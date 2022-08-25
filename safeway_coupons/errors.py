from dataclasses import dataclass
from typing import List

from .accounts import Account
from .models import Offer


@dataclass
class AuthenticationFailure(Exception):
    account: Account


@dataclass
class ClipError(Exception):
    offer: Offer


@dataclass
class TooManyClipErrors(Exception):
    errors: List[ClipError]
