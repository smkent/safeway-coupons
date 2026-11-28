from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from filelock import FileLock

from safeway_coupons.account import Account, AccountsFile
from safeway_coupons.errors import AccountLockedError

if TYPE_CHECKING:
    from pathlib import Path

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
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    accounts_ini: Path,
) -> None:
    main_runner(
        "-a",
        "ness@onett.example",
        "-c",
        str(accounts_ini),
        "--login-only",
        match=0,
    )
    assert (
        "Signing in for Safeway account ness@onett.example" in caplog.messages
    )
