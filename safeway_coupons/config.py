from __future__ import annotations

import configparser
import itertools
import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from .accounts import Account


@dataclass
class Config:
    state_dir_path: Path = field(
        default_factory=lambda: Path(
            platformdirs.user_state_dir(
                appname="safeway-coupons", appauthor="smkent"
            )
        )
    )

    @property
    def state_dir(self) -> Path:
        self.state_dir_path.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            with suppress(PermissionError):
                self.state_dir_path.chmod(mode=0o700)
        return self.state_dir_path

    @state_dir.setter
    def state_dir(self, path: Path) -> None:
        if (new_dir := path.resolve()) != self.state_dir_path.resolve():
            self.state_dir_path = new_dir

    def account_dir(self, account: Account) -> Path:
        path = self.state_dir / "accounts" / account.username.lower()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def load_accounts(cls, config_file: Path | None = None) -> list[Account]:
        account = cls.load_account_from_env()
        if account:
            return [account]
        if config_file:
            accounts = cls.load_accounts_from_config(config_file)
            if accounts:
                return accounts
        return []

    @classmethod
    def load_account_from_env(cls) -> Account | None:
        username = os.environ.get("SAFEWAY_ACCOUNT_USERNAME")
        password = os.environ.get("SAFEWAY_ACCOUNT_PASSWORD")
        mail_to = os.environ.get("SAFEWAY_ACCOUNT_MAIL_TO")
        mail_from = os.environ.get("SAFEWAY_ACCOUNT_MAIL_FROM")
        if username and password:
            return Account(
                username=username,
                password=password,
                mail_to=mail_to or username,
                mail_from=mail_from or username,
            )
        return None

    @classmethod
    def load_accounts_from_config(cls, config_file: Path) -> list[Account]:
        config = configparser.ConfigParser()
        with config_file.open() as f:
            config.read_file(itertools.chain(["[_no_section]"], f))
        accounts: list[Account] = []
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
                Account(
                    username=username,
                    password=config.get(section, "password"),
                    mail_to=mail_to or username,
                    mail_from=mail_from or username,
                )
            )
        return accounts


config = Config()
