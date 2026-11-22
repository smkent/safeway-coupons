from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from safeway_coupons.client.auth import LoginSession
from safeway_coupons.client.browser import SafewayBrowserSession
from safeway_coupons.errors import (
    BrowserSessionError,
    MultiFactorAuthenticationRequired,
    NotSignedIn,
)

if TYPE_CHECKING:
    from pathlib import Path

    from safeway_coupons.account import Account
    from tests.conftest import MainRunner

MFA_REQUIRED = {
    "status": "MFA_REQUIRED",
    "factorResult": "SUCCESS",
    "factors": [
        {
            "id": "factor_id",
            "factorType": "email",
            "profile": {"email": "n***@o***.example"},
        }
    ],
}


def json_response(body: Any) -> MagicMock:
    response = MagicMock()
    response.json.return_value = body
    return response


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (MFA_REQUIRED, "n***@o***.example"),
        (
            {"status": "MFA_REQUIRED", "factors": [{"factorType": "sms"}]},
            "sms",
        ),
        ({"status": "MFA_REQUIRED", "factors": [{}]}, "?"),
        ({"status": "SUCCESS"}, None),
        (["unexpected"], None),
    ],
)
def test_verification_required(
    body: dict[str, Any], expected: str | None
) -> None:
    assert (
        SafewayBrowserSession.verification_required(json_response(body))
        == expected
    )


def test_verification_required_unreadable_response() -> None:
    response = MagicMock()
    response.json.side_effect = ValueError("page reloaded")
    assert SafewayBrowserSession.verification_required(response) is None


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            {"errors": [{"errorCode": "CSMS0120", "message": "Invalid code"}]},
            "Invalid code",
        ),
        (None, "HTTP 400"),
    ],
)
def test_error_message(body: Any, expected: str) -> None:
    response = json_response(body)
    response.status = 400
    assert SafewayBrowserSession.error_message(response) == expected


def test_device_verification_required_from_browser(
    account: Account, mock_browser_driver: MagicMock, tmp_path: Path
) -> None:
    screenshot = tmp_path / "screenshot.png"
    browser = mock_browser_driver.return_value.__enter__.return_value
    error = BrowserSessionError(attachments=[screenshot])
    error.__cause__ = MultiFactorAuthenticationRequired(account)
    browser.sign_in.side_effect = error
    with pytest.raises(MultiFactorAuthenticationRequired) as exc_info:
        LoginSession(account)
    assert exc_info.value.attachments == [screenshot]


def test_device_verification_required(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    accounts_config: Path,
    mock_browser_driver: MagicMock,
) -> None:
    def _raise(*, check: bool) -> None:
        raise MultiFactorAuthenticationRequired(
            mock_browser_driver.call_args.kwargs["account"]
        )

    browser = mock_browser_driver.return_value.__enter__.return_value
    browser.sign_in.side_effect = _raise
    main_runner("-c", str(accounts_config), "--login-only", match=1)
    assert (
        "Error for account ness@onett.example:"
        " ness@onett.example needs an MFA verification code to sign in."
        " Sign in with --login-only from a terminal."
    ) in caplog.messages


def test_browser_error_message_shows_cause(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    accounts_config: Path,
    mock_browser_driver: MagicMock,
) -> None:
    browser = mock_browser_driver.return_value.__enter__.return_value
    error = BrowserSessionError()
    error.__cause__ = RuntimeError("Device verification cancelled")
    browser.sign_in.side_effect = error
    main_runner("-c", str(accounts_config), "--login-only", match=1)
    assert (
        "Error for account ness@onett.example:"
        " Authentication Failure (Device verification cancelled)"
    ) in caplog.messages


def test_check_only_signed_in(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    accounts_config: Path,
    mock_browser_driver: MagicMock,
) -> None:
    browser = mock_browser_driver.return_value.__enter__.return_value
    main_runner(
        "-c", str(accounts_config), "--login-only", "--dry-run", match=0
    )
    browser.sign_in.assert_called_once_with(check=True)
    assert (
        "Checking sign in for Safeway account ness@onett.example"
        in caplog.messages
    )


def test_check_only_not_signed_in(
    caplog: pytest.LogCaptureFixture,
    main_runner: MainRunner,
    accounts_config: Path,
    mock_browser_driver: MagicMock,
) -> None:
    def _raise(*, check: bool) -> None:
        raise NotSignedIn(mock_browser_driver.call_args.kwargs["account"])

    browser = mock_browser_driver.return_value.__enter__.return_value
    browser.sign_in.side_effect = _raise
    main_runner(
        "-c", str(accounts_config), "--login-only", "--dry-run", match=1
    )
    browser.sign_in.assert_called_once_with(check=True)
    assert (
        "Error for account ness@onett.example:"
        " Account ness@onett.example is not signed in"
    ) in caplog.messages
