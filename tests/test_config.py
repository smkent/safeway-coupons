from __future__ import annotations

import stat
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pydantic import Field

from safeway_coupons.account import (
    Account,
    AccountsFile,
    EmailConfig,
    NotifyConfig,
)
from safeway_coupons.models.config import ConfigFile, ConfigModel

if TYPE_CHECKING:
    from tests.utils import CapLogHelper


def paula() -> Account:
    return Account(name="paula", username="paula@twoson.example")


def test_load_default_path(accounts_config: Path) -> None:
    accounts_file = AccountsFile.load()
    assert list(accounts_file.accounts) == ["ness"]
    assert accounts_file.path == accounts_config


def test_load_missing() -> None:
    with pytest.raises(FileNotFoundError):
        AccountsFile.load()


def test_load_missing_ok() -> None:
    accounts_file = AccountsFile.load(missing_ok=True)
    assert accounts_file.accounts == {}
    assert accounts_file.path == AccountsFile.default_path()
    assert not accounts_file.path.exists()


def test_load_missing_ok_save(tmp_path: Path) -> None:
    path = tmp_path / "onett.toml"
    accounts_file = AccountsFile.load(path, missing_ok=True)
    accounts_file.accounts["paula"] = paula()
    accounts_file.save()
    assert list(AccountsFile.load(path).accounts) == ["paula"]
    assert not AccountsFile.default_path().exists()


def test_new_saves_to_default_path() -> None:
    AccountsFile(accounts={"paula": paula()}).save()
    assert list(AccountsFile.load().accounts) == ["paula"]


def test_save_keeps_comments(accounts_config: Path) -> None:
    accounts_config.write_text(
        "# The year is 199X\n" + accounts_config.read_text()
    )
    accounts_file = AccountsFile.load()
    accounts_file.accounts["paula"] = paula()
    accounts_file.save()
    assert accounts_config.read_text().startswith("# The year is 199X\n")
    assert list(AccountsFile.load().accounts) == ["ness", "paula"]


def test_delete(accounts_config: Path) -> None:
    accounts_file = AccountsFile.load()
    accounts_file.delete()
    assert not accounts_config.exists()
    with pytest.raises(FileNotFoundError):
        accounts_file.delete()
    accounts_file.delete(missing_ok=True)


def test_no_default_path() -> None:
    class Town(ConfigFile):
        name: str = ""

    with pytest.raises(ValueError, match="No path for Town"):
        Town.load()
    with pytest.raises(ValueError, match="No path for Town"):
        Town(name="Onett").save()


def test_load_uppercase_name(accounts_config: Path) -> None:
    accounts_config.write_text(
        accounts_config.read_text().replace("accounts.ness", "accounts.Ness")
    )
    accounts = AccountsFile.load().accounts
    assert list(accounts) == ["ness"]
    assert accounts["ness"].name == "ness"


def test_load_names_differing_in_case(accounts_config: Path) -> None:
    accounts_config.write_text(
        accounts_config.read_text()
        + '\n[accounts.NESS]\nusername = "ness@onett.example"\n'
    )
    with pytest.raises(
        ValueError, match=r"accounts\.NESS: name already in use"
    ):
        AccountsFile.load()


def test_load_minimal() -> None:
    path = AccountsFile.default_path()
    path.parent.mkdir(parents=True)
    path.write_text('[accounts.paula]\nusername = "paula@twoson.example"\n')
    assert AccountsFile.load().accounts == {"paula": paula()}


@pytest.mark.parametrize(
    ("mode", "expected_mode"),
    [
        pytest.param(0o644, 0o600, id="0644"),
        pytest.param(0o660, 0o600, id="0660"),
        pytest.param(0o444, 0o400, id="0444"),
        pytest.param(0o600, 0o600, id="0600"),
        pytest.param(0o400, 0o400, id="0400"),
    ],
)
@pytest.mark.parametrize(
    "success",
    [pytest.param(True, id="success"), pytest.param(False, id="failed")],
)
def test_load_corrects_permissions(
    accounts_config: Path,
    caplog_helper: CapLogHelper,
    mode: int,
    expected_mode: int,
    *,
    success: bool,
) -> None:
    accounts_config.chmod(mode)
    if success:
        assert list(AccountsFile.load().accounts) == ["ness"]
        assert stat.S_IMODE(accounts_config.stat().st_mode) == expected_mode
        log_prefix, log_suffix = "Corrected", ""
    else:
        with patch.object(Path, "chmod", side_effect=OSError("BOING!")):
            assert list(AccountsFile.load().accounts) == ["ness"]
        assert stat.S_IMODE(accounts_config.stat().st_mode) == mode
        log_prefix, log_suffix = "Failed to correct", ": BOING!"
    assert caplog_helper.messages == (
        [
            (
                f"{log_prefix} {accounts_config} permissions"
                f" from {mode:04o} to {expected_mode:04o}" + log_suffix
            )
        ]
        if mode != expected_mode
        else []
    )


def test_save_omits_unset_defaults(tmp_path: Path) -> None:

    class Town(ConfigModel):
        name: str
        visited: bool = False

    class Eagleland(ConfigFile):
        towns: dict[str, Town] = Field(default_factory=dict)

    path = tmp_path / "eagleland.toml"
    path.write_text('[towns.onett]\nname = "Onett"\nvisited = false\n')
    eagleland = Eagleland.load(path)
    eagleland.towns["twoson"] = Town(name="Twoson")
    eagleland.towns["threed"] = Town(name="Threed")
    eagleland.towns["threed"].visited = False
    eagleland.save()
    assert path.read_text() == (
        '[towns.onett]\nname = "Onett"\nvisited = false\n\n'
        '[towns.twoson]\nname = "Twoson"\n\n'
        '[towns.threed]\nname = "Threed"\nvisited = false\n'
    )


def test_save_new_tables_as_dotted_keys() -> None:
    AccountsFile(
        accounts={
            "paula": Account(
                name="paula",
                username="paula@twoson.example",
                notify=NotifyConfig(
                    email=EmailConfig(
                        to="ness@onett.example",
                        mail_from="paula@twoson.example",
                    )
                ),
            ),
            "jeff": Account(name="jeff", username="jeff@winters.example"),
        }
    ).save()
    assert AccountsFile.default_path().read_text() == (
        "[accounts.paula]\n"
        'username = "paula@twoson.example"\n'
        'notify.email.to = "ness@onett.example"\n'
        'notify.email.from = "paula@twoson.example"\n'
        "\n"
        "[accounts.jeff]\n"
        'username = "jeff@winters.example"\n'
    )


def test_save_keeps_table_style() -> None:
    path = AccountsFile.default_path()
    path.parent.mkdir(parents=True)
    path.write_text(
        "[accounts.ness]\n"
        'username = "ness@onett.example"\n'
        'notify.email.to = "ness@onett.example"  # Ness\n'
        "\n"
        "[accounts.paula]\n"
        'username = "paula@twoson.example"\n'
        "\n"
        "[accounts.paula.notify.email]\n"
        'to = "ness@onett.example"  # Also Ness\n'
    )
    accounts_file = AccountsFile.load()
    for account in accounts_file.accounts.values():
        assert account.notify
        assert account.notify.email
        account.notify.email.mail_from = "jeff@winters.example"
    accounts_file.save()
    assert path.read_text() == (
        "[accounts.ness]\n"
        'username = "ness@onett.example"\n'
        'notify.email.to = "ness@onett.example"  # Ness\n'
        'notify.email.from = "jeff@winters.example"\n'
        "\n"
        "[accounts.paula]\n"
        'username = "paula@twoson.example"\n'
        "\n"
        "[accounts.paula.notify.email]\n"
        'to = "ness@onett.example"  # Also Ness\n'
        'from = "jeff@winters.example"\n'
    )
