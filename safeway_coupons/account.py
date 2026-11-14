from __future__ import annotations

import configparser
import itertools
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Self

from filelock import FileLock, Timeout

from .dirs import DirsMixin
from .errors import AccountLockedError

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass
class Account(DirsMixin):
    username: str
    password: str = field(repr=False)
    mail_to: str
    mail_from: str

    @cached_property
    def state_subdir(self) -> Path:
        return Path("accounts") / self.username.lower()

    @cached_property
    def lock_file(self) -> Path:
        return self.place_state_file("lock")

    @property
    @contextmanager
    def lock(self) -> Generator[None]:
        try:
            with FileLock(self.lock_file, mode=0o600, blocking=False):
                yield
        except Timeout as e:
            raise AccountLockedError(self) from e

    @classmethod
    def load_from_env(cls) -> Self | None:
        username = os.environ.get("SAFEWAY_ACCOUNT_USERNAME")
        password = os.environ.get("SAFEWAY_ACCOUNT_PASSWORD")
        mail_to = os.environ.get("SAFEWAY_ACCOUNT_MAIL_TO")
        mail_from = os.environ.get("SAFEWAY_ACCOUNT_MAIL_FROM")
        if username and password:
            return cls(
                username=username,
                password=password,
                mail_to=mail_to or username,
                mail_from=mail_from or username,
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
                if config.has_option(section, "email_sender"):
                    mail_from = config.get(section, "email_sender")
                continue
            mail_to = (
                config.get(section, "notify")
                if config.has_option(section, "notify")
                else None
            )
            username = str(section)
            accounts.append(
                cls(
                    username=username,
                    password=config.get(section, "password"),
                    mail_to=mail_to or username,
                    mail_from=mail_from or username,
                )
            )
        return accounts

    @classmethod
    def load_all(cls, config_file: Path | None = None) -> list[Self]:
        account = cls.load_from_env()
        if account:
            return [account]
        if config_file:
            accounts = cls.load_all_from_config(config_file)
            if accounts:
                return accounts
        return []
