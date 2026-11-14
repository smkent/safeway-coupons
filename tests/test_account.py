from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from filelock import FileLock

from safeway_coupons.errors import AccountLockedError

if TYPE_CHECKING:
    from safeway_coupons.account import Account


@pytest.fixture
def new_account(account: Account) -> Account:
    assert not account.lock_file.exists()
    return account


def test_account_lock_nested(new_account: Account) -> None:
    with new_account.lock, pytest.raises(AccountLockedError), new_account.lock:
        pass


def test_account_lock_stale_lock_file(new_account: Account) -> None:
    new_account.lock_file.touch()
    with new_account.lock:
        pass


def test_account_lock_locked(new_account: Account) -> None:
    with (
        FileLock(new_account.lock_file),
        pytest.raises(AccountLockedError),
        new_account.lock,
    ):
        pass


def test_account_lock_released(new_account: Account) -> None:
    for _ in range(2):
        with new_account.lock:
            pass
