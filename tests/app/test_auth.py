from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

import pytest

from safeway_coupons.errors import (
    BrowserSessionError,
    MultiFactorAuthenticationRequired,
)

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from tests.utils import MainRunner, MockMail


@pytest.mark.usefixtures("accounts_toml")
@pytest.mark.parametrize(
    ("argv", "check", "status"),
    [
        pytest.param([], False, "Signing in", id="live"),
        pytest.param(["-p"], True, "Checking sign in", id="dry_run"),
    ],
)
def test_login_only(
    main_runner: MainRunner,
    mail: MockMail,
    mock_browser_driver: MagicMock,
    caplog: pytest.LogCaptureFixture,
    argv: list[str],
    status: str,
    *,
    check: bool,
) -> None:
    main_runner("--login-only", *argv)
    assert (
        mock_browser_driver.sign_in.call_args_list == [call(check=check)] * 2
    )
    for username in ("ness@onett.example", "Paula@twoson.example"):
        assert f"{status} for Safeway account {username}" in caplog.messages
    assert not mail.messages


@pytest.mark.parametrize(
    ("argv", "check", "status"),
    [
        pytest.param([], False, "Signing in", id="live"),
        pytest.param(["-p"], True, "Checking sign in", id="dry_run"),
    ],
)
def test_login_only_legacy_accounts_ini(
    main_runner: MainRunner,
    accounts_ini: Path,
    mail: MockMail,
    mock_browser_driver: MagicMock,
    caplog: pytest.LogCaptureFixture,
    argv: list[str],
    status: str,
    *,
    check: bool,
) -> None:
    main_runner("-c", str(accounts_ini), "--login-only", *argv)
    assert (
        mock_browser_driver.sign_in.call_args_list == [call(check=check)] * 2
    )
    for username in ("ness@onett.example", "Paula@twoson.example"):
        assert f"{status} for Safeway account {username}" in caplog.messages
    assert not mail.messages


@pytest.mark.usefixtures("accounts_toml")
@pytest.mark.parametrize(
    "login_only",
    [pytest.param(False, id="live"), pytest.param(True, id="login_only")],
)
def test_device_verification_required(
    main_runner: MainRunner,
    mail: MockMail,
    mock_browser_driver: MagicMock,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    *,
    login_only: bool,
) -> None:
    def _raise(*, check: bool) -> None:
        screenshot = tmp_path / "screenshot.png"
        screenshot.touch()
        raise MultiFactorAuthenticationRequired(
            mock_browser_driver.account, attachments=[screenshot]
        )

    mock_browser_driver.sign_in.side_effect = _raise
    main_runner(*(["--login-only"] if login_only else []), "--notify", match=1)
    assert mock_browser_driver.sign_in.mock_calls == [call(check=False)] * (
        2 if login_only else 1
    )
    action = "Signing in" if login_only else "Clipping coupons"
    assert (
        f"{action} for Safeway account ness@onett.example" in caplog.messages
    )
    assert (
        "Error for Safeway account ness@onett.example:"
        " Safeway account ness@onett.example needs"
        " an MFA verification code to sign in."
        " Sign in with --login-only from a terminal."
    ) in caplog.messages
    if login_only:
        assert not mail.messages
    else:
        assert len(mail.messages) == 1
        assert mail.attachments(mail.messages[0]) == {"screenshot.png": b""}


@pytest.mark.usefixtures("accounts_toml")
@pytest.mark.parametrize(
    "login_only",
    [pytest.param(False, id="live"), pytest.param(True, id="login_only")],
)
def test_authentication_failure_shows_cause(
    main_runner: MainRunner,
    mail: MockMail,
    mock_browser_driver: MagicMock,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    *,
    login_only: bool,
) -> None:
    def _raise(*, check: bool) -> None:
        screenshot = tmp_path / "screenshot.png"
        screenshot.touch()
        raise BrowserSessionError(attachments=[screenshot]) from RuntimeError(
            "Device verification cancelled"
        )

    mock_browser_driver.sign_in.side_effect = _raise
    main_runner(*(["--login-only"] if login_only else []), "--notify", match=1)
    assert mock_browser_driver.sign_in.mock_calls == [call(check=False)] * (
        2 if login_only else 1
    )
    action = "Signing in" if login_only else "Clipping coupons"
    assert (
        f"{action} for Safeway account ness@onett.example" in caplog.messages
    )
    assert (
        "Error for Safeway account ness@onett.example:"
        " Authentication Failure (Device verification cancelled)"
    ) in caplog.messages
    if login_only:
        assert not mail.messages
    else:
        assert len(mail.messages) == 1
        assert mail.attachments(mail.messages[0]) == {"screenshot.png": b""}
