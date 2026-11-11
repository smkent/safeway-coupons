import os
import sys
from typing import Any
from unittest.mock import patch

import pytest

from safeway_coupons import app
from safeway_coupons.app import main


def test_no_accounts() -> None:
    with (
        patch.object(sys, "argv", ["safeway-coupons"]),
        patch.object(os, "environ", {}),
        pytest.raises(SystemExit),
    ):
        main()


@pytest.mark.parametrize(
    ("debug_level", "expected_exception"),
    [
        (0, SystemExit),
        (1, Exception),
        (2, Exception),
    ],
)
def test_app_error(
    debug_level: int, expected_exception: type[Exception]
) -> None:
    with (
        patch.object(app, "SafewayCoupons") as mock_app,
        patch.object(
            sys, "argv", ["safeway-coupons"] + (["-d"] * debug_level)
        ),
        patch.object(
            os,
            "environ",
            {
                "SAFEWAY_ACCOUNT_USERNAME": "ness@onett.example",
                "SAFEWAY_ACCOUNT_PASSWORD": "pk_fire",
            },
        ),
    ):
        mock_app.return_value.clip_for_account.side_effect = Exception(
            "Test error"
        )
        with pytest.raises(expected_exception):
            main()


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
                "headless": True,
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
                "headless": True,
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
                "headless": True,
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
                "headless": True,
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
                "headless": True,
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
                "headless": True,
            },
            id="Dry run and max clip count",
        ),
    ],
)
def test_args(argv: list[str], expected_args: dict[str, Any]) -> None:
    with (
        patch.object(app, "SafewayCoupons") as mock_app,
        patch.object(sys, "argv", ["safeway-coupons", *argv]),
        patch.object(
            os,
            "environ",
            {
                "SAFEWAY_ACCOUNT_USERNAME": "ness@onett.example",
                "SAFEWAY_ACCOUNT_PASSWORD": "pk_fire",
            },
        ),
    ):
        main()
    mock_app.assert_called_once_with(**expected_args)
