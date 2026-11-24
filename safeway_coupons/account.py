from __future__ import annotations

import configparser
import itertools
import os
import re
import tomllib
from contextlib import contextmanager, suppress
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock, Timeout
from pydantic import ConfigDict, Field, field_validator, model_validator

from .console import log
from .dirs import DirsMixin, dirs
from .errors import AccountLockedError
from .models.config import ConfigFile, ConfigModel
from .models.fields import ItemName, ItemNameT, Password, PasswordT

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any, Self


class EmailConfig(ConfigModel):
    to: str | None = None
    mail_from: str | None = Field(default=None, alias="from")


class NotifyConfig(ConfigModel):
    email: EmailConfig | None = None

    @classmethod
    def for_email(
        cls, *, to: str | None = None, mail_from: str | None = None
    ) -> Self | None:
        if not (to or mail_from):
            return None
        return cls(
            email=EmailConfig(to=to or None, mail_from=mail_from or None)
        )


class Account(ConfigModel, DirsMixin):
    model_config = ConfigDict(validate_assignment=True)

    # Stored as the account's table key in the accounts file, not a value
    name: ItemNameT = Field(exclude=True)
    username: str
    password: PasswordT | None = None
    notify: NotifyConfig | None = None

    @property
    def notify_email(self) -> EmailConfig | None:
        return self.notify.email if self.notify else None

    @cached_property
    def state_subdir(self) -> Path:
        return Path("accounts") / self.name

    @cached_property
    def lock_file(self) -> Path:
        return self.place_state_file("lock")

    @property
    @contextmanager
    def lock(self) -> Generator[None]:
        self._move_legacy_state_dir()
        try:
            with FileLock(self.lock_file, mode=0o600, blocking=False):
                yield
        except Timeout as e:
            raise AccountLockedError(self) from e

    def _move_legacy_state_dir(self) -> None:
        # State directories were previously keyed by lowercased username
        legacy_dir = dirs.state_path("accounts", self.username.lower())
        state_dir = self.state_dir
        if (
            legacy_dir == state_dir
            or legacy_dir.parent != state_dir.parent
            or legacy_dir.name == ".."
            or state_dir.exists()
        ):
            return
        # Another process may have just moved it
        with suppress(FileNotFoundError):
            legacy_dir.rename(state_dir)
            log.info(
                "Migrated state for account %s from %s to %s",
                self.name,
                legacy_dir,
                state_dir,
            )

    @classmethod
    def _name_from_username(cls, username: str) -> str:
        """Derive an account name for accounts configured without one."""
        name = ItemName.INVALID_CHARS.sub("-", username.lower())
        return re.sub(r"^[\W_]+", "", name)

    @classmethod
    def load_from_env(cls) -> Self | None:
        username = os.environ.get("SAFEWAY_ACCOUNT_USERNAME")
        password = os.environ.get("SAFEWAY_ACCOUNT_PASSWORD")
        mail_to = os.environ.get("SAFEWAY_ACCOUNT_MAIL_TO")
        mail_from = os.environ.get("SAFEWAY_ACCOUNT_MAIL_FROM")
        if username and password:
            log.warning(
                "Account configuration with SAFEWAY_ACCOUNT_* environment"
                " variables is deprecated and will be removed in a future"
                " release. Migrate your account to %s.",
                AccountsFile.default_path(),
            )
            return cls(
                name=cls._name_from_username(username),
                username=username,
                password=Password.encode(password),
                notify=NotifyConfig.for_email(to=mail_to, mail_from=mail_from),
            )
        return None

    @classmethod
    def load_all_from_config(cls, config_file: Path) -> list[Self]:
        config = configparser.ConfigParser()
        with config_file.open() as f:
            config.read_file(itertools.chain(["[_no_section]"], f))
        accounts: list[Self] = []
        mail_from = None

        for section in config.sections():
            if section in ["_no_section", "_global"]:
                mail_from = config.get(
                    section, "email_sender", fallback=mail_from
                )
                continue
            username = str(section)
            password = config.get(section, "password", fallback=None)
            mail_to = config.get(section, "notify", fallback=None)
            accounts.append(
                cls(
                    name=cls._name_from_username(username),
                    username=username,
                    password=Password.encode(password) if password else None,
                    notify=NotifyConfig.for_email(
                        to=mail_to, mail_from=mail_from
                    ),
                )
            )
        return accounts

    @classmethod
    def load_all(cls, config_file: Path | None = None) -> list[Account]:
        default_path = AccountsFile.default_path()
        if account := cls.load_from_env():
            log.debug("Loaded account from environment")
            if default_path.is_file():
                log.warning(
                    "Account from environment overrides %s", default_path
                )
            return [account]
        accounts: list[Account] = []
        if path := config_file:
            accounts = (
                list(AccountsFile.load(path).accounts.values())
                if AccountsFile.is_accounts_file(path)
                else list(cls.load_all_from_config(path))
            )
            if (
                default_resolved := default_path.resolve()
            ).is_file() and default_resolved != path.resolve():
                log.warning(
                    "%s via deprecated -c/--accounts-config overrides %s",
                    path,
                    default_path,
                )
        elif (path := default_path).is_file():
            accounts = list(AccountsFile.load(path).accounts.values())
        if path.is_file():
            log.debug("Loaded %d account(s) from %s", len(accounts), path)
        return accounts


class AccountsFile(ConfigFile):
    accounts: dict[ItemNameT, Account] = Field(default_factory=dict)

    @classmethod
    def default_path(cls) -> Path:
        return dirs.config_path("accounts.toml")

    @classmethod
    def is_accounts_file(cls, path: Path) -> bool:
        """Whether a file is in this format, rather than the legacy INI."""
        try:
            data = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError:
            return False
        return isinstance(data.get("accounts"), dict)

    @field_validator("accounts", mode="before")
    @classmethod
    def _names_from_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        accounts = {}
        for key, account in value.items():
            if isinstance(key, str) and key.lower() in (
                k.lower() for k in accounts
            ):
                raise ValueError(
                    f"accounts.{key}: name already in use"
                    " (names are case insensitive)"
                )
            if isinstance(account, dict):
                if "name" in account:
                    raise ValueError(
                        f"accounts.{key}: name is set by the table key,"
                        " not a name value"
                    )
                account = {**account, "name": key}  # noqa: PLW2901
            accounts[key] = account
        return accounts

    @model_validator(mode="after")
    def _check_names(self) -> Self:
        for key, account in self.accounts.items():
            if account.name != key:
                raise ValueError(
                    f"account {account.name!r} is stored under {key!r}"
                )
        return self
