import configparser
import itertools
import os
from typing import List, Optional

from .accounts import Account


class Config:
    @classmethod
    def load_accounts(cls, config_file: Optional[str] = None) -> List[Account]:
        account = cls.load_account_from_env()
        if account:
            return [account]
        if config_file:
            accounts = cls.load_accounts_from_config(config_file)
            if accounts:
                return accounts
        return []

    @classmethod
    def load_account_from_env(cls) -> Optional[Account]:
        username = os.environ.get("SAFEWAY_ACCOUNT_USERNAME")
        password = os.environ.get("SAFEWAY_ACCOUNT_PASSWORD")
        mail_to = os.environ.get("SAFEWAY_ACCOUNT_MAIL_TO")
        mail_from = os.environ.get("SAFEWAY_ACCOUNT_MAIL_TO")
        if username and password:
            return Account(
                username=username,
                password=password,
                mail_to=mail_to or username,
                mail_from=mail_from or username,
            )
        return None

    @classmethod
    def load_accounts_from_config(cls, config_file: str) -> List[Account]:
        config = configparser.ConfigParser()
        with open(config_file) as f:
            config.read_file(itertools.chain(["[_no_section]"], f))
        accounts: List[Account] = []
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
