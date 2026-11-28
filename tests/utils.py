from __future__ import annotations

import email
import email.policy
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self
from unittest.mock import MagicMock, PropertyMock, patch

import platformdirs
import pytest

from safeway_coupons.__main__ import main
from safeway_coupons.dirs import dirs

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from email.message import EmailMessage
    from logging import LogRecord
    from typing import Any, Self

    from tests.conftest import MainRunner


@dataclass
class CapLogHelper:
    caplog: pytest.LogCaptureFixture

    @property
    def messages(self) -> Sequence[str]:
        return self.caplog.messages

    def records(self, message: str) -> Sequence[LogRecord]:
        return [r for r in self.caplog.records if r.getMessage() == message]

    def match_records(self, message: str) -> Sequence[LogRecord]:
        return [r for r in self.caplog.records if message in r.getMessage()]


@dataclass
class MainRunner:
    monkeypatch: pytest.MonkeyPatch

    def __call__(self, *cmd: str, match: int = 0) -> None:
        self.monkeypatch.setattr(sys, "argv", ["safeway-coupons", *cmd])
        with pytest.raises(SystemExit, match=str(match)):
            main()


@dataclass
class MockDirs(ExitStack):
    class Type(Enum):
        StorageDir = auto()
        PlatformDirs = auto()

        @classmethod
        def param(cls, value: Self) -> Any:
            return pytest.param(value, id=value.name.lower())

        @classmethod
        def params(cls) -> Sequence[Any]:
            return tuple(cls.param(t) for t in cls)

    base_storage_dir: Path = field(kw_only=True)
    type: Type = field(kw_only=True)
    user_config_dir: MagicMock = field(init=False, repr=False)
    user_state_dir: MagicMock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        super().__init__()

    @property
    def config(self) -> Path:
        if self.type == self.Type.StorageDir:
            return self.base_storage_dir / "config"
        return self._mock_subdir("config")

    @property
    def state(self) -> Path:
        if self.type == self.Type.StorageDir:
            return self.base_storage_dir / "state"
        return self._mock_subdir("state")

    def __enter__(self) -> Self:
        if self.type == self.Type.StorageDir:
            self.enter_context(
                patch.object(dirs, "base", self.base_storage_dir)
            )
        else:
            for dir_type in ["config", "state"]:
                self._patch_platformdirs_property(dir_type)
            self.enter_context(patch.object(dirs, "base", None))
        return self

    def _mock_subdir(self, dir_type: str) -> Path:
        return self.base_storage_dir / "mock_platformdirs" / dir_type

    def _patch_platformdirs_property(self, dir_type: str) -> Any:
        property_name = f"user_{dir_type}_dir"
        patch_property = patch.object(
            platformdirs.PlatformDirs,
            property_name,
            PropertyMock(return_value=(self._mock_subdir(dir_type))),
        )
        setattr(self, property_name, self.enter_context(patch_property))


@dataclass
class MockMail(ExitStack):
    messages: list[EmailMessage] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__()

    def __enter__(self) -> Self:
        self.enter_context(self.mock_subprocess_sendmail())
        return self

    @contextmanager
    def mock_subprocess_sendmail(self) -> Generator[MagicMock]:
        real_popen = subprocess.Popen

        def _save_message(message: bytes, *_: Any, **__: Any) -> None:
            self.messages.append(
                email.message_from_bytes(message, policy=email.policy.default)
            )

        def _popen(cmd: Sequence[str], *args: Any, **kwargs: Any) -> Any:
            if Path(cmd[0]).name == "sendmail":
                return MagicMock(communicate=_save_message)
            return real_popen(cmd, *args, **kwargs)

        with patch.object(
            subprocess, "Popen", autospec=True, side_effect=_popen
        ) as obj:
            yield obj

    @classmethod
    def attachments(cls, message: EmailMessage) -> dict[str | None, Any]:
        return {
            part.get_filename(): part.get_content()
            for part in message.iter_attachments()
        }

    @classmethod
    def screenshot(cls, message: EmailMessage) -> bytes:
        return cls.attachments(message)["screenshot.png"]
