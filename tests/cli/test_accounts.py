from __future__ import annotations

import getpass
import io
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from safeway_coupons.account import (
    Account,
    AccountsFile,
    EmailConfig,
    NotifyConfig,
)
from safeway_coupons.brands import Brand
from safeway_coupons.models.fields import Password
from tests.utils import CapLogHelper, MainRunner, MockDirs

from .utils import ExpectedOutput

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .utils import OutputTest


LEGACY_ACCOUNTS = {
    "ness@onett.example": Account(
        brand=Brand.Safeway,
        name="ness@onett.example",
        username="ness@onett.example",
        password=Password.encode("pk_fire"),
        notify=NotifyConfig(email=EmailConfig(mail_from="ness@onett.example")),
    ),
    "paula@twoson.example": Account(
        brand=Brand.Safeway,
        name="paula@twoson.example",
        username="Paula@twoson.example",
        password=Password.encode("pk_freeze"),
        notify=NotifyConfig(
            email=EmailConfig(
                to="ness@onett.example", mail_from="ness@onett.example"
            )
        ),
    ),
}


@pytest.fixture(params=["account", "accounts"])
def accounts_command(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(autouse=True)
def mock_getpass() -> Iterator[MagicMock]:
    with patch.object(getpass, "getpass", side_effect=[""]) as obj:
        yield obj


@pytest.fixture(params=MockDirs.Type.params())
def mock_dirs_type(request: pytest.FixtureRequest) -> MockDirs.Type:
    return request.param


@pytest.fixture
def accounts_toml_single_account(accounts_toml: Path) -> Path:
    """accounts.toml with ness, which has saved state, and paula."""
    config = AccountsFile.load(accounts_toml)
    del config.accounts["paula"]
    config.save()
    return accounts_toml


@pytest.fixture
def renamable_account(accounts_toml: Path) -> Account:
    """accounts.toml with ness, which has saved state, and paula."""
    config = AccountsFile.load(accounts_toml)
    config.accounts["paula"] = Account(
        name="paula", username="paula@twoson.example"
    )
    config.save()
    account = config.accounts["ness"]
    with account.lock:
        (account.state_dir / "state.json").write_text("{}")
    return account


def get_saved_password(name: str) -> str | None:
    password = AccountsFile.load().accounts[name].password
    return password.get_secret_value() if password else None


def test_accounts_path(
    output_test: OutputTest, mock_dirs: MockDirs, accounts_command: str
) -> None:
    path = mock_dirs.config / "accounts.toml"
    output_test.expected = ExpectedOutput(stdout=f"{path}\n")
    output_test(accounts_command, "path")


@pytest.mark.parametrize("command", ["list", "ls"])
def test_accounts_list(
    output_test: OutputTest, accounts_command: str, command: str
) -> None:
    accounts = AccountsFile(
        accounts={
            "ness@onett.example": Account(
                name="ness@onett.example",
                username="ness@onett.example",
                password=Password.encode("pk_fire"),
                notify=None,
            ),
            "paula@twoson.example": Account(
                name="paula@twoson.example",
                brand="albertsons",
                username="paula@twoson.example",
                password=None,
                notify=NotifyConfig(
                    email=EmailConfig(
                        mail_from=None,
                        to="ness@onett.example",
                    )
                ),
            ),
        }
    )
    accounts.save(AccountsFile.default_path())
    output_test(accounts_command, command)


@pytest.mark.parametrize("command", ["list", "ls"])
def test_accounts_list_empty(
    output_test: OutputTest, accounts_command: str, command: str
) -> None:
    output_test.expected = ExpectedOutput(
        stdout=f"No accounts configured in {AccountsFile.default_path()}\n"
    )
    output_test(accounts_command, command)


def test_accounts_list_env_account(
    main_runner: MainRunner,
    caplog_helper: CapLogHelper,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
) -> None:
    monkeypatch.setenv("SAFEWAY_ACCOUNT_USERNAME", "paula@twoson.example")
    monkeypatch.setenv("SAFEWAY_ACCOUNT_PASSWORD", "pk_fire")
    main_runner(accounts_command, "list", match=1)
    assert (
        "Account configured with environment variables"
        " cannot be used with accounts management commands."
    ) in caplog_helper.messages


def test_accounts_list_legacy_config(
    main_runner: MainRunner,
    caplog_helper: CapLogHelper,
    accounts_command: str,
    tmp_path: Path,
) -> None:
    legacy_config = tmp_path / "legacy_accounts"
    legacy_config.write_text("[paula@twoson.example]\npassword = pk_fire\n")
    main_runner("-c", str(legacy_config), accounts_command, "list", match=1)
    assert (
        "-c/--accounts-config is deprecated"
        " and cannot be used with accounts management commands."
    ) in caplog_helper.messages


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("Ness From Onett", id="spaces"),
        pytest.param("ness/onett", id="slash"),
        pytest.param("-ness", id="leading-dash"),
        pytest.param(".ness", id="leading-dot"),
    ],
)
def test_accounts_add_invalid_name(
    output_test: OutputTest, accounts_command: str, name: str
) -> None:
    output_test.expected = ExpectedOutput(
        logs=[
            (
                f'Invalid account name "{name}": must start with a letter'
                " or number, and can't contain spaces or slashes"
            ),
        ]
    )
    output_test(accounts_command, "add", "--", "safeway", name, match=1)
    assert not AccountsFile.default_path().exists()


@pytest.mark.parametrize("name", ["ness", "Ness"])
def test_accounts_add_new_file(
    output_test: OutputTest,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
    name: str,
) -> None:
    monkeypatch.setattr("getpass.getpass", lambda *_, **__: "pk_fire")
    output_test.expected = ExpectedOutput(
        stdout="Sign in password: Confirm password: ",
        logs=['Account "ness" saved.'],
    )
    output_test(
        accounts_command,
        "add",
        "safeway",
        name,
        "ness@onett.example",
        "-t",
        "",
        "-f",
        "",
    )
    assert (
        AccountsFile.default_path()
        .read_text()
        .startswith('[accounts.ness]\nbrand = "safeway"\n')
    )
    assert AccountsFile.load().accounts == {
        "ness": Account(
            brand=Brand.Safeway,
            name="ness",
            username="ness@onett.example",
            password=Password.encode("pk_fire"),
        )
    }


@pytest.mark.parametrize(
    "brand", ["jewelosco", "JewelOsco", "Jewel-Osco", "jewelosco.com"]
)
def test_accounts_add_brand(
    output_test: OutputTest,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
    brand: str,
) -> None:
    monkeypatch.setattr("getpass.getpass", lambda *_, **__: "pk_fire")
    output_test.expected = ExpectedOutput(
        stdout="Sign in password: Confirm password: ",
        logs=['Account "ness" saved.'],
    )
    output_test(
        accounts_command,
        "add",
        brand,
        "ness",
        "ness@onett.example",
        "-t",
        "",
        "-f",
        "",
    )
    assert AccountsFile.load().accounts == {
        "ness": Account(
            name="ness",
            username="ness@onett.example",
            password=Password.encode("pk_fire"),
            brand=Brand.JewelOsco,
        )
    }


def test_accounts_add_unknown_brand(
    main_runner: MainRunner, accounts_command: str
) -> None:
    main_runner(
        accounts_command,
        "add",
        "machpizza",
        "ness",
        "ness@onett.example",
        match=2,
    )
    assert not AccountsFile.default_path().exists()


def test_accounts_add_prompt_unknown_brand(
    output_test: OutputTest,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
) -> None:
    monkeypatch.setattr("getpass.getpass", lambda *_, **__: "pk_fire")
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("machpizza\nAlbertsons\nness\nness@onett.example\n"),
    )
    output_test.expected = ExpectedOutput(
        stdout=(
            "Store brand (safeway): Store brand (safeway): "
            "Account name (will be converted to lower case): "
            "Sign in email address: "
            "Sign in password: Confirm password: "
        ),
        logs=[
            "'machpizza' is not a valid brand, use one of: "
            + ", ".join(repr(b.value) for b in Brand),
            'Account "ness" saved.',
        ],
    )
    output_test(accounts_command, "add", "-t", "", "-f", "")
    assert AccountsFile.load().accounts["ness"].brand == Brand.Albertsons


def test_accounts_add_no_sign_in_email(
    output_test: OutputTest,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    output_test.expected = ExpectedOutput(
        stdout="Sign in email address: ",
        logs=["Sign in email address is required"],
    )
    output_test(accounts_command, "add", "safeway", "ness", match=1)
    assert not AccountsFile.default_path().exists()


def test_accounts_add_existing_file(
    output_test: OutputTest,
    mock_getpass: MagicMock,
    accounts_toml_single_account: Path,
    accounts_command: str,
) -> None:
    ness = AccountsFile.load(accounts_toml_single_account).accounts["ness"]
    mock_getpass.side_effect = ["pk_freeze", "pk_freeze"]
    output_test.expected = ExpectedOutput(
        stdout="Sign in password: Confirm password: ",
        logs=['Account "paula" saved.'],
    )
    output_test(
        accounts_command,
        "add",
        "safeway",
        "paula",
        "paula@twoson.example",
        "--email-to",
        "ness@onett.example",
        "--email-from",
        "paula@twoson.example",
    )
    assert AccountsFile.load().accounts == {
        "ness": ness,
        "paula": Account(
            name="paula",
            username="paula@twoson.example",
            password=Password.encode("pk_freeze"),
            notify=NotifyConfig(
                email=EmailConfig(
                    to="ness@onett.example", mail_from="paula@twoson.example"
                )
            ),
        ),
    }


@pytest.mark.parametrize("name", ["ness", "Ness"])
def test_accounts_add_existing_name(
    output_test: OutputTest,
    accounts_toml: Path,
    accounts_command: str,
    name: str,
) -> None:
    original = accounts_toml.read_text()
    output_test.expected = ExpectedOutput(
        logs=['An account named "ness" is already configured']
    )
    output_test(
        accounts_command,
        "add",
        "safeway",
        name,
        "ninten@podunk.example",
        match=1,
    )
    assert accounts_toml.read_text() == original


def test_accounts_add_prompts(
    output_test: OutputTest,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("\nJeff\njeff@winters.example\nness@onett.example\n\n"),
    )
    output_test.expected = ExpectedOutput(
        stdout=(
            "Store brand (safeway): "
            "Account name (will be converted to lower case): "
            "Sign in email address: "
            "Sign in password: "
            "Notification email recipient (optional): "
            "Notification email sender (optional): "
        ),
        logs=['Account "jeff" saved.'],
    )
    output_test(accounts_command, "add")
    assert (
        AccountsFile.default_path()
        .read_text()
        .startswith('[accounts.jeff]\nbrand = "safeway"\n')
    )
    assert AccountsFile.load().accounts == {
        "jeff": Account(
            name="jeff",
            brand=Brand.Safeway,
            username="jeff@winters.example",
            notify=NotifyConfig(email=EmailConfig(to="ness@onett.example")),
        )
    }


@pytest.mark.usefixtures("accounts_toml")
@pytest.mark.parametrize("name", ["ness", "Ness"])
def test_accounts_remove(
    output_test: OutputTest, accounts_command: str, name: str
) -> None:
    config = AccountsFile.load()
    config.accounts["paula"] = Account(
        name="paula", username="paula@twoson.example"
    )
    config.save()
    output_test.expected = ExpectedOutput(logs=['Account "ness" removed.'])
    output_test(accounts_command, "rm", name, "-y")
    assert list(AccountsFile.load().accounts) == ["paula"]


@pytest.mark.usefixtures("accounts_toml_single_account")
def test_accounts_remove_last(
    output_test: OutputTest, accounts_command: str
) -> None:
    output_test.expected = ExpectedOutput(logs=['Account "ness" removed.'])
    output_test(accounts_command, "remove", "ness", "-y")
    assert not AccountsFile.default_path().exists()


@pytest.mark.usefixtures("accounts_toml")
def test_accounts_remove_keeps_state(
    output_test: OutputTest, accounts_command: str
) -> None:
    account = AccountsFile.load().accounts["ness"]
    with account.lock:
        pass
    output_test.expected = ExpectedOutput(
        logs=[
            'Account "ness" removed.',
            (
                'Saved browser state for "ness" was kept at'
                f" {account.state_dir}. Delete it if you no longer need it."
            ),
        ]
    )
    output_test(accounts_command, "remove", "ness", "-y")
    assert (account.state_dir / "lock").is_file()


def test_accounts_remove_no_accounts(
    output_test: OutputTest, accounts_command: str
) -> None:
    output_test.expected = ExpectedOutput(
        logs=['No account named "ness" is configured']
    )
    output_test(accounts_command, "remove", "ness", "-y", match=1)
    assert not AccountsFile.default_path().exists()


@pytest.mark.parametrize("command", ["add", "set-password", "remove", "list"])
def test_accounts_help_with_env_account(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
    command: str,
) -> None:
    monkeypatch.setenv("SAFEWAY_ACCOUNT_USERNAME", "paula@twoson.example")
    monkeypatch.setenv("SAFEWAY_ACCOUNT_PASSWORD", "pk_fire")
    main_runner(accounts_command, command, "--help")


@pytest.mark.usefixtures("accounts_toml")
@pytest.mark.parametrize("command", ["set-password", "password"])
def test_accounts_set_password(
    output_test: OutputTest,
    mock_getpass: MagicMock,
    accounts_command: str,
    command: str,
) -> None:
    value = "pk_thunder"
    mock_getpass.side_effect = [value, value]
    output_test.expected = ExpectedOutput(
        stdout="Sign in password: Confirm password: ",
        logs=['Account "ness" password set.'],
    )
    output_test(accounts_command, command, "ness")
    assert get_saved_password("ness") == value
    assert (
        f'password = "{Password.encode(value)}"'
        in AccountsFile.default_path().read_text()
    )


@pytest.mark.usefixtures("accounts_toml")
def test_accounts_set_password_mismatch(
    output_test: OutputTest, mock_getpass: MagicMock, accounts_command: str
) -> None:
    mock_getpass.side_effect = ["pk_thunder", "pk__thunder"]
    output_test.expected = ExpectedOutput(
        stdout="Sign in password: Confirm password: ",
        logs=["Passwords do not match"],
    )
    output_test(accounts_command, "set-password", "ness", match=1)
    assert get_saved_password("ness") == "pk_fire"


@pytest.mark.usefixtures("accounts_toml")
def test_accounts_set_password_empty(
    output_test: OutputTest, accounts_command: str
) -> None:
    output_test.expected = ExpectedOutput(
        stdout="Sign in password: ",
        logs=[
            (
                "No password entered."
                " To remove a saved password,"
                " use the `accounts clear-password` command."
            ),
        ],
    )
    output_test(accounts_command, "set-password", "ness", match=1)
    assert get_saved_password("ness") == "pk_fire"


@pytest.mark.parametrize("command", ["set-password", "clear-password"])
def test_accounts_password_no_account(
    output_test: OutputTest, accounts_command: str, command: str
) -> None:
    output_test.expected = ExpectedOutput(
        logs=['No account named "ness" is configured']
    )
    output_test(accounts_command, command, "ness", match=1)
    assert not AccountsFile.default_path().exists()


@pytest.mark.usefixtures("accounts_toml_single_account")
def test_accounts_clear_password(
    output_test: OutputTest, accounts_command: str
) -> None:
    output_test.expected = ExpectedOutput(
        logs=['Account "ness" password cleared.']
    )
    output_test(accounts_command, "clear-password", "ness", "-y")
    assert get_saved_password("ness") is None
    assert "password" not in AccountsFile.default_path().read_text()


def test_accounts_clear_password_not_set(
    output_test: OutputTest, accounts_command: str
) -> None:
    AccountsFile(
        accounts={
            "paula": Account(name="paula", username="paula@twoson.example")
        }
    ).save()
    output_test.expected = ExpectedOutput(
        logs=['Account "paula" has no password set.']
    )
    output_test(accounts_command, "clear-password", "paula")


def import_log(
    path: Path, *, count: int = 2, dry_run: bool = False
) -> list[str]:
    dry_run_suffix = " (dry run)" if dry_run else ""
    summary = "Would import" if dry_run else "Imported"
    return [
        f"Importing accounts from {path}{dry_run_suffix}",
        (
            'Importing account "ness@onett.example" with sign in name'
            ' "ness@onett.example"'
        ),
        (
            'Importing account "paula@twoson.example" with sign in name'
            ' "Paula@twoson.example"'
        ),
        f"{summary} {count} account(s)",
    ]


def test_accounts_import(
    output_test: OutputTest, accounts_command: str, accounts_ini: Path
) -> None:
    output_test.expected = ExpectedOutput(logs=import_log(accounts_ini))
    output_test(accounts_command, "import", str(accounts_ini))
    assert AccountsFile.load().accounts == LEGACY_ACCOUNTS
    saved = AccountsFile.default_path().read_text()
    assert saved.count('brand = "safeway"') == len(LEGACY_ACCOUNTS)


@pytest.mark.parametrize(
    "accounts_file_env",
    [pytest.param(False, id="option"), pytest.param(True, id="docker")],
)
def test_accounts_import_accounts_config_option(
    output_test: OutputTest,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
    accounts_ini: Path,
    *,
    accounts_file_env: bool,
) -> None:
    path = AccountsFile.default_path()
    if accounts_file_env:
        monkeypatch.setenv("SAFEWAY_ACCOUNTS_FILE", str(accounts_ini))
        next_step = "Remove SAFEWAY_ACCOUNTS_FILE and its volume mount"
    else:
        next_step = "Stop passing -c/--accounts-config"
    output_test.expected = ExpectedOutput(
        logs=[
            (
                "-c/--accounts-config is deprecated and will be removed in a"
                f" future release. Migrate your accounts to {path}."
            ),
            *import_log(accounts_ini),
            (
                f"Accounts are now configured in {path}. {next_step}"
                " so it is used."
            ),
        ]
    )
    output_test("-c", str(accounts_ini), accounts_command, "import")
    assert AccountsFile.load().accounts == LEGACY_ACCOUNTS


def test_accounts_import_existing(
    output_test: OutputTest, accounts_command: str, accounts_ini: Path
) -> None:
    AccountsFile(
        accounts={
            "ness@onett.example": Account(
                name="ness@onett.example", username="ness@onett.example"
            )
        }
    ).save()
    output_test.expected = ExpectedOutput(
        logs=[
            f"Importing accounts from {accounts_ini}",
            (
                'Not importing account "ness@onett.example", which matches an'
                " existing account"
            ),
            (
                'Importing account "paula@twoson.example" with sign in name'
                ' "Paula@twoson.example"'
            ),
            "Imported 1 account(s)",
        ]
    )
    output_test(accounts_command, "import", str(accounts_ini))
    accounts = AccountsFile.load().accounts
    assert accounts["ness@onett.example"].password is None
    assert (
        accounts["paula@twoson.example"]
        == (LEGACY_ACCOUNTS["paula@twoson.example"])
    )


def test_accounts_import_same_derived_name(
    output_test: OutputTest, accounts_command: str, tmp_path: Path
) -> None:
    path = tmp_path / "legacy_accounts"
    path.write_text(
        "[ness onett@eagleland.example]\npassword = pk_fire\n"
        "[ness/onett@eagleland.example]\npassword = pk_fire\n"
    )
    output_test.expected = ExpectedOutput(
        logs=[
            f"Importing accounts from {path}",
            (
                'Importing account "ness-onett@eagleland.example" with'
                ' sign in name "ness onett@eagleland.example"'
            ),
            (
                'Not importing sign in name "ness/onett@eagleland.example",'
                " since it has the same account name"
                ' "ness-onett@eagleland.example" as sign in name'
                ' "ness onett@eagleland.example"'
            ),
            "Imported 1 account(s)",
        ]
    )
    output_test(accounts_command, "import", str(path))
    accounts = AccountsFile.load().accounts
    assert [a.username for a in accounts.values()] == [
        "ness onett@eagleland.example"
    ]


def test_accounts_import_dry_run(
    output_test: OutputTest, accounts_command: str, accounts_ini: Path
) -> None:
    output_test.expected = ExpectedOutput(
        logs=import_log(accounts_ini, dry_run=True)
    )
    output_test(accounts_command, "import", "--dry-run", str(accounts_ini))
    assert not AccountsFile.default_path().exists()


def test_accounts_import_nothing(
    output_test: OutputTest, accounts_command: str, tmp_path: Path
) -> None:
    path = tmp_path / "legacy_accounts"
    path.write_text("")
    output_test.expected = ExpectedOutput(
        logs=[f"Importing accounts from {path}", "Imported 0 account(s)"]
    )
    output_test(accounts_command, "import", str(path))
    assert not AccountsFile.default_path().exists()


def test_accounts_import_accounts_toml_format(
    output_test: OutputTest, accounts_command: str, tmp_path: Path
) -> None:
    path = tmp_path / "other_accounts.toml"
    paula = Account(
        name="paula",
        brand=Brand.Safeway,
        username="paula@twoson.example",
        password=Password.encode("pk_freeze"),
    )
    AccountsFile(accounts={"paula": paula}).save(path)
    output_test.expected = ExpectedOutput(
        logs=[
            f"Importing accounts from {path}",
            (
                'Importing account "paula" with sign in name'
                ' "paula@twoson.example"'
            ),
            "Imported 1 account(s)",
        ]
    )
    output_test(accounts_command, "import", str(path))
    assert AccountsFile.load().accounts == {"paula": paula}
    assert (
        AccountsFile.default_path()
        .read_text()
        .startswith('[accounts.paula]\nbrand = "safeway"\n')
    )


def test_accounts_import_env_account(
    main_runner: MainRunner,
    caplog_helper: CapLogHelper,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
    accounts_ini: Path,
) -> None:
    monkeypatch.setenv("SAFEWAY_ACCOUNT_USERNAME", "ness@onett.example")
    monkeypatch.setenv("SAFEWAY_ACCOUNT_PASSWORD", "pk_fire")
    main_runner(accounts_command, "import", str(accounts_ini), match=1)
    assert (
        "Account configured with environment variables"
        " cannot be used with accounts management commands."
    ) in caplog_helper.messages
    assert not AccountsFile.default_path().exists()


def test_accounts_import_no_source(
    output_test: OutputTest, accounts_command: str
) -> None:
    output_test.expected = ExpectedOutput(logs=["No import file specified."])
    output_test(accounts_command, "import", match=1)


@pytest.mark.parametrize("command", ["rename", "mv"])
def test_accounts_rename(
    output_test: OutputTest,
    accounts_command: str,
    renamable_account: Account,
    command: str,
) -> None:
    ness = AccountsFile.load().accounts["ness"]
    output_test.expected = ExpectedOutput(
        logs=['Account "ness" renamed to "jeff".']
    )
    output_test(accounts_command, command, "Ness", "Jeff")
    accounts = AccountsFile.load().accounts
    assert set(accounts) == {"jeff", "paula"}
    assert accounts["jeff"] == ness.model_copy(update={"name": "jeff"})
    assert not renamable_account.state_dir.exists()
    assert (accounts["jeff"].state_dir / "state.json").is_file()


def test_accounts_rename_keeps_place(
    output_test: OutputTest, accounts_command: str
) -> None:
    def accounts_toml(name: str) -> str:
        return (
            "# Onett\n"
            "[accounts.ness]  # Ness\n"
            'username = "ness@onett.example"\n'
            "\n"
            "# Twoson\n"
            f"[accounts.{name}]  # Paula\n"
            'username = "paula@twoson.example"\n'
            f"[accounts.{name}.notify.email]\n"
            'to = "ness@onett.example"  # Ness again\n'
            "\n"
            "# Winters\n"
            "[accounts.jeff]  # Jeff\n"
            'username = "jeff@winters.example"\n'
        )

    path = AccountsFile.default_path()
    path.parent.mkdir(parents=True)
    path.write_text(accounts_toml("paula"))
    path.chmod(0o600)
    with AccountsFile.load().accounts["paula"].lock:
        pass  # Creates the state directory to be moved
    output_test.expected = ExpectedOutput(
        logs=['Account "paula" renamed to "paula-again".']
    )
    output_test(accounts_command, "rename", "paula", "paula-again")
    assert path.read_text() == accounts_toml("paula-again")


def test_accounts_rename_existing_name(
    output_test: OutputTest, accounts_command: str, renamable_account: Account
) -> None:
    output_test.expected = ExpectedOutput(
        logs=['An account named "paula" is already configured']
    )
    output_test(accounts_command, "rename", "ness", "paula", match=1)
    assert list(AccountsFile.load().accounts) == ["ness", "paula"]
    assert (renamable_account.state_dir / "state.json").is_file()


def test_accounts_rename_invalid_name(
    output_test: OutputTest, accounts_command: str, renamable_account: Account
) -> None:
    output_test.expected = ExpectedOutput(
        logs=[
            (
                'Invalid account name "ninten/ana": must start with a'
                " letter or number, and can't contain spaces or slashes"
            ),
        ]
    )
    output_test(accounts_command, "rename", "ness", "ninten/ana", match=1)
    assert list(AccountsFile.load().accounts) == ["ness", "paula"]
    assert (renamable_account.state_dir / "state.json").is_file()


def test_accounts_rename_no_account(
    output_test: OutputTest, accounts_command: str
) -> None:
    output_test.expected = ExpectedOutput(
        logs=['No account named "ness" is configured']
    )
    output_test(accounts_command, "rename", "ness", "jeff", match=1)
    assert not AccountsFile.default_path().exists()


def test_accounts_rename_state_exists(
    output_test: OutputTest, accounts_command: str, renamable_account: Account
) -> None:
    jeff_state = renamable_account.state_dir.parent / "jeff"
    jeff_state.mkdir()
    output_test.expected = ExpectedOutput(
        logs=[
            f"{jeff_state} already exists. Move or delete it, then try again.",
        ]
    )
    output_test(accounts_command, "rename", "ness", "jeff", match=1)
    assert list(AccountsFile.load().accounts) == ["ness", "paula"]
    assert (renamable_account.state_dir / "state.json").is_file()


def test_accounts_rename_locked(
    output_test: OutputTest, accounts_command: str, renamable_account: Account
) -> None:
    output_test.expected = ExpectedOutput(
        logs=[
            (
                "Safeway account ness@onett.example is in use"
                " by another process, try again later"
            ),
        ]
    )
    with renamable_account.lock:
        output_test(accounts_command, "rename", "ness", "jeff", match=1)
    assert list(AccountsFile.load().accounts) == ["ness", "paula"]
    assert (renamable_account.state_dir / "state.json").is_file()


def test_accounts_rename_save_fails(
    main_runner: MainRunner,
    monkeypatch: pytest.MonkeyPatch,
    accounts_command: str,
    renamable_account: Account,
) -> None:
    def _fail(*_: object, **__: object) -> None:
        raise OSError("Disk full")

    monkeypatch.setattr(Path, "replace", _fail)
    with pytest.raises(OSError, match="Disk full"):
        main_runner(accounts_command, "rename", "ness", "jeff")
    assert list(AccountsFile.load().accounts) == ["ness", "paula"]
    assert (renamable_account.state_dir / "state.json").is_file()
    assert not (renamable_account.state_dir.parent / "jeff").exists()
