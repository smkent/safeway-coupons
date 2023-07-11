import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Type, cast
from unittest import mock

import pytest
import pytest_mock

from safeway_coupons import app
from safeway_coupons.app import main


def test_no_accounts(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["safeway-coupons"])
    mocker.patch.object(os, "environ", {})
    with pytest.raises(SystemExit):
        main()


@pytest.mark.parametrize(
    ["debug_level", "expected_exception"],
    [
        (0, SystemExit),
        (1, Exception),
        (2, Exception),
    ],
)
def test_app_error(
    mocker: pytest_mock.MockerFixture,
    debug_level: int,
    expected_exception: Type[Exception],
) -> None:
    mocker.patch.object(app, "SafewayCoupons")
    mocker.patch.object(
        sys, "argv", ["safeway-coupons"] + (["-d"] * debug_level)
    )
    mocker.patch.object(
        os,
        "environ",
        {
            "SAFEWAY_ACCOUNT_USERNAME": "ness@onett.example",
            "SAFEWAY_ACCOUNT_PASSWORD": "pk_fire",
        },
    )
    cast(
        mock.MagicMock, app.SafewayCoupons
    ).return_value.clip_for_account.side_effect = Exception("Test error")
    with pytest.raises(expected_exception):
        main()


@pytest.mark.parametrize(
    ["argv", "expected_args"],
    [
        (
            [],
            dict(
                send_email=True,
                sendmail=["/usr/sbin/sendmail"],
                debug_level=0,
                debug_dir=Path("."),
                sleep_level=0,
                dry_run=False,
                max_clip_count=0,
            ),
        ),
        (
            ["-d", "-d", "-SS"],
            dict(
                send_email=True,
                sendmail=["/usr/sbin/sendmail"],
                debug_level=2,
                debug_dir=Path("."),
                sleep_level=2,
                dry_run=False,
                max_clip_count=0,
            ),
        ),
        (
            ["--sendmail", "/my/special/sendmail"],
            dict(
                send_email=True,
                sendmail=["/my/special/sendmail"],
                debug_level=0,
                debug_dir=Path("."),
                sleep_level=0,
                dry_run=False,
                max_clip_count=0,
            ),
        ),
        (
            [
                "--sendmail",
                (
                    "/my/special/sendmail "
                    '--do-the-thing "with an argument value with spaces"'
                ),
            ],
            dict(
                send_email=True,
                sendmail=[
                    "/my/special/sendmail",
                    "--do-the-thing",
                    "with an argument value with spaces",
                ],
                debug_level=0,
                debug_dir=Path("."),
                sleep_level=0,
                dry_run=False,
                max_clip_count=0,
            ),
        ),
        (
            ["-n"],
            dict(
                send_email=False,
                sendmail=["/usr/sbin/sendmail"],
                debug_level=0,
                debug_dir=Path("."),
                sleep_level=0,
                dry_run=False,
                max_clip_count=0,
            ),
        ),
        (
            ["-p", "--max-clip", "42"],
            dict(
                send_email=True,
                sendmail=["/usr/sbin/sendmail"],
                debug_level=0,
                debug_dir=Path("."),
                sleep_level=0,
                dry_run=True,
                max_clip_count=42,
            ),
        ),
    ],
    ids=[
        "Default values",
        "Debug and sleep levels 2",
        "Custom sendmail",
        "Custom sendmail with arguments",
        "No email",
        "Dry run and max clip count",
    ],
)
def test_args(
    mocker: pytest_mock.MockerFixture,
    argv: List[str],
    expected_args: Dict[str, Any],
) -> None:
    mocker.patch.object(app, "SafewayCoupons")
    mocker.patch.object(sys, "argv", ["safeway-coupons"] + argv)
    mocker.patch.object(
        os,
        "environ",
        {
            "SAFEWAY_ACCOUNT_USERNAME": "ness@onett.example",
            "SAFEWAY_ACCOUNT_PASSWORD": "pk_fire",
        },
    )
    main()
    cast(mock.MagicMock, app.SafewayCoupons).assert_called_once_with(
        **expected_args
    )
