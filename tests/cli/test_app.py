from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from safeway_coupons.app import SafewayCoupons
from safeway_coupons.dirs import dirs
from safeway_coupons.errors import Error
from tests.accounts import ACCOUNTS_TOML, LEGACY_ACCOUNTS_INI

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from tests.utils import CapLogHelper, MainRunner


@pytest.fixture(autouse=True)
def mock_clip() -> Iterator[MagicMock]:
    with patch.object(SafewayCoupons, "clip_for_account") as obj:
        yield obj


def test_no_accounts(
    main_runner: MainRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    main_runner(match=1)


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
    [record] = caplog_helper.records("Error for account ness@onett.example: ")
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
    main_runner: MainRunner, argv: list[str], expected_instance: SafewayCoupons
) -> None:
    with patch.object(SafewayCoupons, "__call__", autospec=True) as mock_app:
        main_runner(*argv)
    mock_app.assert_called_once()
    assert mock_app.call_args.args[0] == expected_instance


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


@pytest.mark.parametrize(
    "custom_storage_dir",
    [pytest.param(True, id="present"), pytest.param(False, id="absent")],
)
def test_accounts_toml(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    mock_clip: MagicMock,
    tmp_path: Path,
    custom_storage_dir: bool,  # noqa: FBT001
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    storage_dir = tmp_path / "custom-storage"
    config_dir = storage_dir / "config" if custom_storage_dir else dirs.config
    config_dir.mkdir(parents=True)
    (config_dir / "accounts.toml").write_text(ACCOUNTS_TOML)
    args = ["--storage-dir", str(storage_dir)] if custom_storage_dir else []
    main_runner(*args)
    assert mock_clip.call_count == 2
    for name in ("ness", "paula"):
        assert (dirs.state / "accounts" / name / "lock").is_file()


@pytest.mark.parametrize(
    ("config_content", "account_names"),
    [
        pytest.param(ACCOUNTS_TOML, ("ness", "paula"), id="toml"),
        pytest.param(
            LEGACY_ACCOUNTS_INI,
            ("ness@onett.example", "paula@twoson.example"),
            id="ini",
        ),
    ],
)
def test_accounts_config_option(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    mock_clip: MagicMock,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    config_content: str,
    account_names: tuple[str, ...],
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    accounts_config = tmp_path / "accounts-config"
    accounts_config.write_text(config_content)
    main_runner("-c", str(accounts_config))
    assert mock_clip.call_count == 2
    for name in account_names:
        assert (dirs.state / "accounts" / name / "lock").is_file()
    assert any(
        "-c/--accounts-config is deprecated" in m for m in caplog.messages
    )


@pytest.mark.parametrize("source", ["env", "ini"])
def test_legacy_username_with_plus(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    mock_clip: MagicMock,
    tmp_path: Path,
    source: str,
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    username = "ness+mani-mani@onett.example"
    legacy_dir = dirs.state / "accounts" / username
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "state.json").write_text("{}")
    if source == "env":
        monkeypatch.setenv("SAFEWAY_ACCOUNT_USERNAME", username)
        monkeypatch.setenv("SAFEWAY_ACCOUNT_PASSWORD", "pk_fire")
        main_runner()
    else:
        accounts_config = tmp_path / "accounts-config"
        accounts_config.write_text(f"[{username}]\npassword = pk_fire\n")
        main_runner("-c", str(accounts_config))
    mock_clip.assert_called_once()
    assert (legacy_dir / "state.json").is_file()
    assert (legacy_dir / "lock").is_file()


@pytest.mark.parametrize(
    "new_state_exists",
    [pytest.param(True, id="exists"), pytest.param(False, id="absent")],
)
def test_legacy_state_dir_moved(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    mock_clip: MagicMock,
    caplog: pytest.LogCaptureFixture,
    new_state_exists: bool,  # noqa: FBT001
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    dirs.config.mkdir(parents=True)
    (dirs.config / "accounts.toml").write_text(ACCOUNTS_TOML)
    legacy_dir = dirs.state / "accounts" / "paula@twoson.example"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "state.json").write_text("{}")
    new_dir = dirs.state / "accounts" / "paula"
    if new_state_exists:
        new_dir.mkdir(parents=True)
    main_runner()
    assert mock_clip.call_count == 2
    if new_state_exists:
        assert (legacy_dir / "state.json").is_file()
        assert not (new_dir / "state.json").exists()
        assert not any("Migrated state" in m for m in caplog.messages)
    else:
        assert not legacy_dir.exists()
        assert (new_dir / "state.json").is_file()
        assert (
            f"Migrated state for account paula from {legacy_dir} to {new_dir}"
            in caplog.messages
        )


@pytest.fixture(
    params=(pytest.param(True, id="present"), pytest.param(False, id="absent"))
)
def accounts_toml_setup(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Path:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    accounts_toml = dirs.config / "accounts.toml"
    if request.param:
        accounts_toml.parent.mkdir(parents=True)
        accounts_toml.write_text(ACCOUNTS_TOML)
    return accounts_toml


def test_accounts_source_logged_env(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    accounts_toml_setup: Path,
) -> None:
    monkeypatch.setenv("SAFEWAY_ACCOUNT_USERNAME", "jeff@winters.example")
    monkeypatch.setenv("SAFEWAY_ACCOUNT_PASSWORD", "bottle_rocket")
    main_runner("--verbose")
    assert (
        "Account configuration with SAFEWAY_ACCOUNT_* environment variables"
        " is deprecated and will be removed in a future release."
        f" Migrate your account to {accounts_toml_setup}."
    ) in caplog.messages
    assert "Loaded account from environment" in caplog.messages
    found = (
        f"Account from environment overrides {accounts_toml_setup}"
        in caplog.messages
    )
    assert found is accounts_toml_setup.is_file()


def test_accounts_source_logged_ini(
    main_runner: MainRunner,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    accounts_toml_setup: Path,
) -> None:
    accounts_config = tmp_path / "accounts-config"
    accounts_config.write_text(LEGACY_ACCOUNTS_INI)
    main_runner("--verbose", "-c", str(accounts_config))
    assert f"Loaded 2 account(s) from {accounts_config}" in caplog.messages
    found = (
        f"{accounts_config} via deprecated -c/--accounts-config"
        f" overrides {accounts_toml_setup}"
    ) in caplog.messages
    assert found is accounts_toml_setup.is_file()


@pytest.mark.parametrize(
    "with_accounts_config_arg",
    [
        pytest.param(True, id="accounts-config-arg"),
        pytest.param(False, id="no-args"),
    ],
)
def test_accounts_source_logged_toml(
    main_runner: MainRunner,
    caplog: pytest.LogCaptureFixture,
    *,
    with_accounts_config_arg: bool,
) -> None:
    accounts_toml = dirs.config / "accounts.toml"
    accounts_toml.parent.mkdir(parents=True)
    accounts_toml.write_text(ACCOUNTS_TOML)
    main_runner(
        "--verbose",
        *(["-c", str(accounts_toml)] if with_accounts_config_arg else []),
    )
    assert f"Loaded 2 account(s) from {accounts_toml}" in caplog.messages
    assert not any(
        "via deprecated -c/--accounts-config overrides" in m
        for m in caplog.messages
    )
