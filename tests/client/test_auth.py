from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from safeway_coupons.account import AccountsFile
from safeway_coupons.client.auth import LoginSession
from safeway_coupons.errors import (
    BrowserSessionError,
    MultiFactorAuthenticationRequired,
    NotSignedIn,
)

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from tests.utils import MainRunner


@pytest.mark.usefixtures("accounts_toml")
def test_device_verification_required_from_browser(
    mock_browser_driver: MagicMock, tmp_path: Path
) -> None:
    account = AccountsFile.load().accounts["ness"]
    screenshot = tmp_path / "screenshot.png"
    error = BrowserSessionError(attachments=[screenshot])
    error.__cause__ = MultiFactorAuthenticationRequired(account)
    mock_browser_driver.sign_in.side_effect = error
    with pytest.raises(MultiFactorAuthenticationRequired) as exc_info:
        LoginSession(account)
    assert exc_info.value.attachments == [screenshot]


@pytest.mark.usefixtures("accounts_toml")
def test_device_verification_required(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    mock_browser_driver: MagicMock,
) -> None:
    def _raise(*, check: bool) -> None:
        raise MultiFactorAuthenticationRequired(mock_browser_driver.account)

    mock_browser_driver.sign_in.side_effect = _raise
    main_runner("-a", "ness", "--login-only", match=1)
    assert (
        "Error for account ness@onett.example:"
        " ness@onett.example needs an MFA verification code to sign in."
        " Sign in with --login-only from a terminal."
    ) in caplog.messages


@pytest.mark.usefixtures("accounts_toml")
def test_browser_error_message_shows_cause(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    mock_browser_driver: MagicMock,
) -> None:
    error = BrowserSessionError()
    error.__cause__ = RuntimeError("Device verification cancelled")
    mock_browser_driver.sign_in.side_effect = error
    main_runner("-a", "ness", "--login-only", match=1)
    assert (
        "Error for account ness@onett.example:"
        " Authentication Failure (Device verification cancelled)"
    ) in caplog.messages


@pytest.mark.usefixtures("accounts_toml")
def test_check_only_signed_in(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    mock_browser_driver: MagicMock,
) -> None:
    main_runner("-a", "ness", "--login-only", "--dry-run", match=0)
    mock_browser_driver.sign_in.assert_called_once_with(check=True)
    assert (
        "Checking sign in for Safeway account ness@onett.example"
        in caplog.messages
    )


@pytest.mark.usefixtures("accounts_toml")
def test_check_only_not_signed_in(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    mock_browser_driver: MagicMock,
) -> None:
    def _raise(*, check: bool) -> None:
        raise NotSignedIn(mock_browser_driver.account)

    mock_browser_driver.sign_in.side_effect = _raise
    main_runner("-a", "ness", "--login-only", "--dry-run", match=1)
    mock_browser_driver.sign_in.assert_called_once_with(check=True)
    assert (
        "Error for account ness@onett.example:"
        " Account ness@onett.example is not signed in"
    ) in caplog.messages
