from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import responses
import rich

from safeway_coupons.account import (
    Account,
    AccountsFile,
    EmailConfig,
    NotifyConfig,
)
from safeway_coupons.client.browser import SafewayBrowserSession
from safeway_coupons.console import console
from safeway_coupons.models.fields import Password

from .accounts import ACCOUNTS_TOML
from .utils import CapLogHelper, MainRunner, MockDirs, MockMail

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


pytest.register_assert_rewrite("tests.cli.utils")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "browser: Playwright browser based tests with a mock site"
    )


@pytest.fixture(autouse=True)
def console_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr(rich, "_console", None)
    console.configure()


@pytest.fixture(autouse=True)
def mock_stdin_isatty() -> Iterator[None]:
    with patch.object(sys.stdin, "isatty", return_value=False):
        yield


@pytest.fixture
def main_runner(monkeypatch: pytest.MonkeyPatch) -> MainRunner:
    return MainRunner(monkeypatch=monkeypatch)


@pytest.fixture(params=[MockDirs.Type.param(MockDirs.Type.StorageDir)])
def mock_dirs_type(request: pytest.FixtureRequest) -> MockDirs.Type:
    return request.param


@pytest.fixture(autouse=True)
def mock_dirs(
    tmp_path: Path, *, mock_dirs_type: MockDirs.Type
) -> Iterator[MockDirs]:
    base_storage_dir = tmp_path / "storage"
    with MockDirs(
        base_storage_dir=base_storage_dir, type=mock_dirs_type
    ) as pd:
        yield pd


@pytest.fixture(autouse=True)
def mail() -> Iterator[MockMail]:
    with MockMail() as mock_mail:
        yield mock_mail


@pytest.fixture
def caplog_helper(caplog: pytest.LogCaptureFixture) -> CapLogHelper:
    return CapLogHelper(caplog=caplog)


@pytest.fixture
def http_responses() -> Iterator[responses.RequestsMock]:
    with responses.RequestsMock() as resp_mock:
        yield resp_mock


@pytest.fixture
def mock_browser_driver_enter() -> Iterator[MagicMock]:
    with patch.object(
        SafewayBrowserSession, "__enter__", autospec=True
    ) as obj:
        yield obj


@pytest.fixture(autouse=True)
def mock_browser_driver(mock_browser_driver_enter: MagicMock) -> MagicMock:
    instance = create_autospec(SafewayBrowserSession, instance=True)
    instance.user_agent = "UnitTestUserAgent/1.0"

    def _enter(self: SafewayBrowserSession) -> MagicMock:
        instance.account = self.account
        return instance

    mock_browser_driver_enter.side_effect = _enter
    return instance


@pytest.fixture
def account() -> Account:
    return Account(
        name="ness",
        username="ness@onett.example",
        password=Password.encode("pk_fire"),
        notify=NotifyConfig(
            email=EmailConfig(
                to="ness@onett.example", mail_from="ness@onett.example"
            )
        ),
    )


@pytest.fixture
def accounts_toml() -> Path:
    accounts_file = AccountsFile.default_path()
    accounts_file.parent.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text(ACCOUNTS_TOML)
    accounts_file.chmod(0o600)
    return accounts_file


@pytest.fixture
def accounts_config() -> Path:
    accounts_file = AccountsFile.default_path()
    accounts_file.parent.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text(
        os.linesep.join(
            (
                "[accounts.ness]",
                'username = "ness@onett.example"',
                f'password = "{Password.encode("pk_fire")}"',
            )
        )
    )
    accounts_file.chmod(0o600)
    return accounts_file
