from __future__ import annotations

import os
from contextlib import nullcontext
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from safeway_coupons.account import Account
from safeway_coupons.dirs import dirs
from safeway_coupons.errors import Error
from safeway_coupons.safeway import SafewayCoupons

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import MainRunner


def test_no_accounts(
    main_runner: MainRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    main_runner(match=1)


@pytest.mark.parametrize(
    ("debug_level", "expected_exception"), [(0, None), (1, Error), (2, Error)]
)
def test_app_error(
    main_runner: MainRunner,
    debug_level: int,
    expected_exception: type[Exception] | None,
) -> None:
    with (
        patch.object(SafewayCoupons, "clip_for_account", side_effect=Error()),
        patch.object(
            os,
            "environ",
            {
                "SAFEWAY_ACCOUNT_USERNAME": "ness@onett.example",
                "SAFEWAY_ACCOUNT_PASSWORD": "pk_fire",
            },
        ),
        pytest.raises(expected_exception)
        if expected_exception
        else nullcontext(),
    ):
        main_runner(*(["-d"] * debug_level), match=1)


@pytest.mark.parametrize(
    ("argv", "expected_instance"),
    [
        pytest.param(
            [],
            SafewayCoupons(sendmail=["/usr/sbin/sendmail"]),
            id="Default values",
        ),
        pytest.param(
            ["-d", "-d", "-SS"],
            SafewayCoupons(
                debug_level=2, sleep_level=2, sendmail=["/usr/sbin/sendmail"]
            ),
            id="Debug and sleep levels 2",
        ),
        pytest.param(
            ["--sendmail", "/my/special/sendmail"],
            SafewayCoupons(sendmail=["/my/special/sendmail"]),
            id="Custom sendmail",
        ),
        pytest.param(
            [
                "--sendmail",
                (
                    "/my/special/sendmail "
                    '--do-the-thing "with an argument value with spaces"'
                ),
            ],
            SafewayCoupons(
                sendmail=[
                    "/my/special/sendmail",
                    "--do-the-thing",
                    "with an argument value with spaces",
                ]
            ),
            id="Custom sendmail with arguments",
        ),
        pytest.param(
            ["-n"],
            SafewayCoupons(send_email=False, sendmail=["/usr/sbin/sendmail"]),
            id="No email",
        ),
        pytest.param(
            ["-p", "--max-clip", "42"],
            SafewayCoupons(
                dry_run=True,
                max_clip_count=42,
                sendmail=["/usr/sbin/sendmail"],
            ),
            id="Dry run and max clip count",
        ),
        pytest.param(
            ["-E"],
            SafewayCoupons(
                continue_on_error=True,
                sendmail=["/usr/sbin/sendmail"],
            ),
            id="Continue on error",
        ),
        pytest.param(
            ["-H"],
            SafewayCoupons(headless=False, sendmail=["/usr/sbin/sendmail"]),
            id="No headless",
        ),
    ],
)
def test_args(
    main_runner: MainRunner, argv: list[str], expected_instance: SafewayCoupons
) -> None:
    with (
        patch.object(SafewayCoupons, "__call__", autospec=True) as mock_app,
        patch.object(
            os,
            "environ",
            {
                "SAFEWAY_ACCOUNT_USERNAME": "ness@onett.example",
                "SAFEWAY_ACCOUNT_PASSWORD": "pk_fire",
            },
        ),
    ):
        main_runner(*argv)
    mock_app.assert_called_once()
    expected_instance.accounts = [
        Account(
            username="ness@onett.example",
            password="pk_fire",  # noqa: S106
            mail_to="ness@onett.example",
            mail_from="ness@onett.example",
        )
    ]
    assert mock_app.call_args.args[0] == expected_instance


def test_args_state_dir(
    main_runner: MainRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SAFEWAY_ACCOUNT_USERNAME", "Ness@onett.example")
    monkeypatch.setenv("SAFEWAY_ACCOUNT_PASSWORD", "pk_fire")
    state_dir = tmp_path / "custom-state"
    with patch.object(SafewayCoupons, "clip_for_account") as mock_clip:
        main_runner("-s", str(state_dir))
    mock_clip.assert_called_once()
    lock_file = state_dir / "accounts" / "ness@onett.example" / "lock"
    assert lock_file.is_file()
    assert dirs.state == state_dir.resolve()
