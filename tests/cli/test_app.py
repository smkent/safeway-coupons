from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from safeway_coupons.app import SafewayCoupons
from safeway_coupons.dirs import dirs
from safeway_coupons.errors import Error

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from tests.utils import CapLogHelper, MainRunner


@pytest.fixture(autouse=True)
def mock_clip() -> Iterator[MagicMock]:
    with patch.object(SafewayCoupons, "clip_for_account") as obj:
        yield obj


@pytest.mark.parametrize(
    "verbosity_argument",
    [pytest.param("-d", id="debug"), pytest.param("-v", id="verbose")],
)
@pytest.mark.parametrize("verbosity", [0, 1, 2])
def test_app_error(
    main_runner: MainRunner,
    caplog_helper: CapLogHelper,
    mock_clip: MagicMock,
    verbosity_argument: str,
    verbosity: int,
) -> None:
    mock_clip.side_effect = Error
    with (
        patch.object(
            os,
            "environ",
            {
                "SAFEWAY_ACCOUNT_USERNAME": "ness@onett.example",
                "SAFEWAY_ACCOUNT_PASSWORD": "pk_fire",
            },
        ),
    ):
        main_runner(*([verbosity_argument] * verbosity), match=1)
    mock_clip.assert_called_once()
    [record] = caplog_helper.records(
        "Error for Safeway account ness@onett.example: "
    )
    if verbosity:
        assert len(
            caplog_helper.records(
                "-d/--debug is deprecated, use -v/--verbose instead"
            )
        ) == (1 if verbosity_argument == "-d" else 0)
        assert record.exc_info
        assert record.exc_info[0] is Error
    else:
        assert not record.exc_info
    assert "Error clipping coupons for 1 accounts" in caplog_helper.messages


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
            SafewayCoupons(sleep_level=2, sendmail=["/usr/sbin/sendmail"]),
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
            ["-N"],
            SafewayCoupons(send_email=True, sendmail=["/usr/sbin/sendmail"]),
            id="Notification",
        ),
        pytest.param(
            ["-n"],
            SafewayCoupons(send_email=False, sendmail=["/usr/sbin/sendmail"]),
            id="No notification",
        ),
        pytest.param(
            ["--no-email"],
            SafewayCoupons(send_email=False, sendmail=["/usr/sbin/sendmail"]),
            id="Deprecated no email option",
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
        pytest.param(
            ["--login-only", "-p"],
            SafewayCoupons(
                login_only=True,
                dry_run=True,
                sendmail=["/usr/sbin/sendmail"],
            ),
            id="Login only dry run",
        ),
    ],
)
def test_args(
    main_runner: MainRunner,
    caplog_helper: CapLogHelper,
    argv: list[str],
    expected_instance: SafewayCoupons,
) -> None:
    with patch.object(SafewayCoupons, "__call__", autospec=True) as mock_app:
        main_runner(*argv)
    mock_app.assert_called_once()
    assert mock_app.call_args.args[0] == expected_instance
    assert len(
        caplog_helper.records(
            "--no-email is deprecated, use -n/--no-notify instead"
        )
    ) == (1 if "--no-email" in argv else 0)


@pytest.mark.parametrize(
    "isatty",
    [pytest.param(True, id="tty"), pytest.param(False, id="not-a-tty")],
)
def test_args_notify_default(main_runner: MainRunner, *, isatty: bool) -> None:
    with (
        patch.object(SafewayCoupons, "__call__", autospec=True) as mock_app,
        patch.object(sys.stdin, "isatty", return_value=isatty),
    ):
        main_runner()
    mock_app.assert_called_once()
    assert mock_app.call_args.args[0] == SafewayCoupons(
        send_email=not isatty, sendmail=["/usr/sbin/sendmail"]
    )


def test_args_storage_dir(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    mock_clip: MagicMock,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SAFEWAY_ACCOUNT_USERNAME", "Ness@onett.example")
    monkeypatch.setenv("SAFEWAY_ACCOUNT_PASSWORD", "pk_fire")
    storage_dir = tmp_path / "custom-storage"
    main_runner("--storage-dir", str(storage_dir))
    mock_clip.assert_called_once()
    lock_file = (
        storage_dir / "state" / "accounts" / "ness@onett.example" / "lock"
    )
    assert lock_file.is_file()
    assert dirs.state == (storage_dir / "state").resolve()
