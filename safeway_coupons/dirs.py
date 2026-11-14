from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import platformdirs

if TYPE_CHECKING:
    import os

APP_NAME = "safeway-coupons"
APP_AUTHOR = "smkent"


@dataclass
class Dirs:
    state: Path = field(
        default_factory=lambda: platformdirs.user_state_path(
            appname=APP_NAME, appauthor=APP_AUTHOR
        )
    )

    def state_path(self, *parts: str | os.PathLike[str]) -> Path:
        return self.state.joinpath(*parts)

    def place_state_file(self, *parts: str | os.PathLike[str]) -> Path:
        path = self.state_path(*parts)
        missing = [p for p in (path.parent, *path.parents) if not p.exists()]
        for p in reversed(missing):
            p.mkdir(mode=0o700, exist_ok=True)
        return path


class DirsMixin:
    @property
    def state_subdir(self) -> Path:
        return Path()

    @property
    def state_dir(self) -> Path:
        return dirs.state_path(self.state_subdir)

    def place_state_file(self, name: str | os.PathLike[str]) -> Path:
        return dirs.place_state_file(self.state_subdir, name)


dirs = Dirs()
