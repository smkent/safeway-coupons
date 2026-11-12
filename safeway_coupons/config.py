from __future__ import annotations

import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs


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


config = Config()
