from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from filelock import FileLock

from safeway_coupons.account import Account, AccountsFile
from safeway_coupons.errors import AccountLockedError

from .accounts import LEGACY_ACCOUNTS, LEGACY_ACCOUNTS_INI

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from safeway_coupons.account import Account
    from tests.conftest import MainRunner


@pytest.fixture
def new_account(accounts_toml: Path) -> Account:
    account = AccountsFile.load().accounts["ness"]
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


def test_legacy_accounts_config_with_browser_session(
    main_runner: MainRunner,
    tmp_path: Path,
    mock_browser_driver_enter: MagicMock,
) -> None:
    accounts_file = tmp_path / "test_accounts"
    accounts_file.write_text(LEGACY_ACCOUNTS_INI)
    main_runner("-c", str(accounts_file), "--login-only", match=0)
    assert {
        account.name: account
        for call in mock_browser_driver_enter.call_args_list
        if (account := call.args[0].account)
    } == LEGACY_ACCOUNTS
