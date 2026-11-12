from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from filelock import FileLock

from safeway_coupons.errors import AccountLockedError

from .utils import create_account

if TYPE_CHECKING:
    from safeway_coupons.accounts import Account


@pytest.fixture
def account() -> Account:
    new_account = create_account()
    assert not new_account.lock_file.exists()
    return new_account


def test_account_lock_nested(account: Account) -> None:
    with account, pytest.raises(AccountLockedError), account:
        pass


def test_account_lock_stale_lock_file(account: Account) -> None:
    account.lock_file.touch()
    with account:
        pass


def test_account_lock_locked(account: Account) -> None:
    with (
        FileLock(account.lock_file),
        pytest.raises(AccountLockedError),
        account,
    ):
        pass


def test_account_lock_released(account: Account) -> None:
    for _ in range(2):
        with account:
            pass
