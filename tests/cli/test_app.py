from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from safeway_coupons import __main__ as main
from safeway_coupons.safeway import SafewayCoupons

if TYPE_CHECKING:
    from tests.conftest import MainRunner


def test_no_accounts(main_runner: MainRunner) -> None:
    with patch.object(os, "environ", {}):
        main_runner(match=1)


@pytest.mark.parametrize(
    ("debug_level", "expected_exception"),
    [
        (0, None),
        (1, Exception),
        (2, Exception),
    ],
)
def test_app_error(
    main_runner: MainRunner,
    debug_level: int,
    expected_exception: type[Exception] | None,
) -> None:
    with (
        patch.object(
            SafewayCoupons,
            "clip_for_account",
            side_effect=Exception("Test error"),
        ),
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
    ("argv", "expected_args"),
    [
        pytest.param(
            [],
            {
                "send_email": True,
                "sendmail": ["/usr/sbin/sendmail"],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": False,
                "headless": True,
                "accounts_config": None,
                "state_dir": None,
            },
            id="Default values",
        ),
        pytest.param(
            ["-d", "-d", "-SS"],
            {
                "send_email": True,
                "sendmail": ["/usr/sbin/sendmail"],
                "debug_level": 2,
                "sleep_level": 2,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": False,
                "headless": True,
                "accounts_config": None,
                "state_dir": None,
            },
            id="Debug and sleep levels 2",
        ),
        pytest.param(
            ["--sendmail", "/my/special/sendmail"],
            {
                "send_email": True,
                "sendmail": ["/my/special/sendmail"],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": False,
                "headless": True,
                "accounts_config": None,
                "state_dir": None,
            },
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
            {
                "send_email": True,
                "sendmail": [
                    "/my/special/sendmail",
                    "--do-the-thing",
                    "with an argument value with spaces",
                ],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": False,
                "headless": True,
                "accounts_config": None,
                "state_dir": None,
            },
            id="Custom sendmail with arguments",
        ),
        pytest.param(
            ["-n"],
            {
                "send_email": False,
                "sendmail": ["/usr/sbin/sendmail"],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": False,
                "headless": True,
                "accounts_config": None,
                "state_dir": None,
            },
            id="No email",
        ),
        pytest.param(
            ["-p", "--max-clip", "42"],
            {
                "send_email": True,
                "sendmail": ["/usr/sbin/sendmail"],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": True,
                "max_clip_count": 42,
                "continue_on_error": False,
                "headless": True,
                "accounts_config": None,
                "state_dir": None,
            },
            id="Dry run and max clip count",
        ),
        pytest.param(
            ["-E"],
            {
                "send_email": True,
                "sendmail": ["/usr/sbin/sendmail"],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": True,
                "headless": True,
                "accounts_config": None,
                "state_dir": None,
            },
            id="Continue on error",
        ),
        pytest.param(
            ["-H"],
            {
                "send_email": True,
                "sendmail": ["/usr/sbin/sendmail"],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": False,
                "headless": False,
                "accounts_config": None,
                "state_dir": None,
            },
            id="No headless",
        ),
        pytest.param(
            ["-c", "some-file.ini"],
            {
                "send_email": True,
                "sendmail": ["/usr/sbin/sendmail"],
                "debug_level": 0,
                "sleep_level": 0,
                "dry_run": False,
                "max_clip_count": 0,
                "continue_on_error": False,
                "headless": True,
                "accounts_config": Path("some-file.ini"),
                "state_dir": None,
            },
            id="Accounts configuration file",
        ),
    ],
)
def test_args(
    main_runner: MainRunner, argv: list[str], expected_args: dict[str, Any]
) -> None:
    with (
        patch.object(main, "SafewayCoupons") as mock_app,
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
    mock_app.assert_called_once_with(**expected_args)
