from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from platformdirs import PlatformDirs

if TYPE_CHECKING:
    import os

APP_NAME = "safeway-coupons"
APP_AUTHOR = "smkent"


@dataclass
class Dirs:
    base: Path | None = None
    platformdirs: ClassVar[PlatformDirs] = PlatformDirs(APP_NAME, APP_AUTHOR)

    @property
    def state(self) -> Path:
        if self.base:
            return self.base / "state"
        return self.platformdirs.user_state_path

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
