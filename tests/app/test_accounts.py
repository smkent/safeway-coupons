from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from safeway_coupons.app import SafewayCoupons
from safeway_coupons.dirs import dirs

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from unittest.mock import MagicMock

    from tests.utils import MainRunner


@pytest.fixture(autouse=True)
def mock_clip() -> Iterator[MagicMock]:
    with patch.object(SafewayCoupons, "clip_for_account") as obj:
        yield obj


@pytest.fixture(
    params=(pytest.param(True, id="present"), pytest.param(False, id="absent"))
)
def accounts_toml_setup(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    accounts_toml: Path,
) -> Path:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    if not request.param:
        accounts_toml.unlink(missing_ok=True)
    return accounts_toml


def test_no_accounts(
    main_runner: MainRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    main_runner(match=1)


@pytest.mark.parametrize(
    "custom_storage_dir",
    [pytest.param(True, id="present"), pytest.param(False, id="absent")],
)
def test_accounts_toml(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    mock_clip: MagicMock,
    accounts_toml: Path,
    tmp_path: Path,
    custom_storage_dir: bool,  # noqa: FBT001
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    storage_dir = tmp_path / "custom-storage"
    if custom_storage_dir:
        config_dir = storage_dir / "config"
        config_dir.mkdir(parents=True)
        accounts_toml.rename(config_dir / "accounts.toml")
    args = ["--storage-dir", str(storage_dir)] if custom_storage_dir else []
    main_runner(*args)
    assert mock_clip.call_count == 2
    for name in ("ness", "paula"):
        assert (dirs.state / "accounts" / name / "lock").is_file()


@pytest.mark.parametrize(
    ("config_content", "account_name"),
    [
        pytest.param(
            '[accounts.ness]\nusername = "ness@onett.example"\n',
            "ness",
            id="toml",
        ),
        pytest.param(
            "[ness@onett.example]\npassword = pk_fire\n",
            "ness@onett.example",
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
    account_name: str,
) -> None:
    for kk in [k for k in os.environ if k.startswith("SAFEWAY_")]:
        monkeypatch.delenv(kk)
    accounts_config = tmp_path / "accounts-config"
    accounts_config.write_text(config_content)
    main_runner("-c", str(accounts_config))
    mock_clip.assert_called_once()
    assert (dirs.state / "accounts" / account_name / "lock").is_file()
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


@pytest.mark.usefixtures("accounts_toml")
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
    accounts_ini: Path,
    caplog: pytest.LogCaptureFixture,
    accounts_toml_setup: Path,
) -> None:
    main_runner("--verbose", "-c", str(accounts_ini))
    assert f"Loaded 2 account(s) from {accounts_ini}" in caplog.messages
    found = (
        f"{accounts_ini} via deprecated -c/--accounts-config"
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
    accounts_toml: Path,
    *,
    with_accounts_config_arg: bool,
) -> None:
    main_runner(
        "--verbose",
        *(["-c", str(accounts_toml)] if with_accounts_config_arg else []),
    )
    assert f"Loaded 2 account(s) from {accounts_toml}" in caplog.messages
    assert not any(
        "via deprecated -c/--accounts-config overrides" in m
        for m in caplog.messages
    )


@pytest.mark.usefixtures("accounts_toml")
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param([], ["ness", "paula"], id="none"),
        pytest.param(["-a", "paula"], ["paula"], id="single"),
        pytest.param(["--account", "Ness"], ["ness"], id="lowercase-match"),
        pytest.param(
            ["-a", "paula", "-a", "ness", "-a", "PAULA"],
            ["paula", "ness"],
            id="order",
        ),
    ],
)
def test_account_option(
    main_runner: MainRunner,
    mock_clip: MagicMock,
    args: list[str],
    expected: list[str],
) -> None:
    main_runner(*args)
    assert [c.args[0].name for c in mock_clip.call_args_list] == expected


@pytest.mark.usefixtures("accounts_toml")
def test_account_option_login_only(
    main_runner: MainRunner, caplog: pytest.LogCaptureFixture
) -> None:
    main_runner("--login-only", "-a", "paula")
    assert [m for m in caplog.messages if m.startswith("Signing in")] == [
        "Signing in for Safeway account Paula@twoson.example"
    ]


@pytest.mark.usefixtures("accounts_toml")
@pytest.mark.parametrize(
    ("args", "unknown_account_names"),
    [
        pytest.param(["-a", "jeff"], ["jeff"], id="single"),
        pytest.param(
            ["-a", "AppleKid", "-a", "ness", "-a", "orange/kid"],
            ["applekid", "orange/kid"],
            id="multiple",
        ),
    ],
)
def test_account_option_unknown(
    main_runner: MainRunner,
    mock_clip: MagicMock,
    caplog: pytest.LogCaptureFixture,
    args: list[str],
    unknown_account_names: list[str],
) -> None:
    main_runner(*args, match=1)
    mock_clip.assert_not_called()
    assert [m for m in caplog.messages if m.startswith("No account")] == [
        f'No account named "{name}" is configured'
        for name in unknown_account_names
    ]
