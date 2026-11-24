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
    def config(self) -> Path:
        if self.base:
            return self.base / "config"
        return self.platformdirs.user_config_path

    @property
    def state(self) -> Path:
        if self.base:
            return self.base / "state"
        return self.platformdirs.user_state_path

    def config_path(self, *parts: str | os.PathLike[str]) -> Path:
        return self.config.joinpath(*parts)

    def place_config_file(self, *parts: str | os.PathLike[str]) -> Path:
        path = self.config_path(*parts)
        self.mkdirs(path.parent)
        return path

    def state_path(self, *parts: str | os.PathLike[str]) -> Path:
        return self.state.joinpath(*parts)

    def place_state_file(self, *parts: str | os.PathLike[str]) -> Path:
        path = self.state_path(*parts)
        self.mkdirs(path.parent)
        return path

    def mkdirs(self, path: Path) -> None:
        missing = [p for p in (path, *path.parents) if not p.exists()]
        for p in reversed(missing):
            p.mkdir(mode=0o700, exist_ok=True)


class DirsMixin:
    @property
    def config_subdir(self) -> Path:
        return Path()

    @property
    def config_dir(self) -> Path:
        return dirs.config_path(self.config_subdir)

    def place_config_file(self, name: str | os.PathLike[str]) -> Path:
        return dirs.place_config_file(self.config_subdir, name)

    @property
    def state_subdir(self) -> Path:
        return Path()

    @property
    def state_dir(self) -> Path:
        return dirs.state_path(self.state_subdir)

    def place_state_file(self, name: str | os.PathLike[str]) -> Path:
        return dirs.place_state_file(self.state_subdir, name)


dirs = Dirs()
