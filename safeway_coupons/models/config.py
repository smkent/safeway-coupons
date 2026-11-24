from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self

import tomlkit
from pydantic import BaseModel, ConfigDict, PrivateAttr

from safeway_coupons.console import log
from safeway_coupons.dirs import dirs

if TYPE_CHECKING:
    from collections.abc import Iterator


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # New tables nested this deep are written as dotted keys,
    # e.g. `notify.email.to = ...` within `[accounts.main]`
    dotted_key_depth: ClassVar[int] = 2

    @classmethod
    def _update(cls, table: Any, data: dict[str, Any], depth: int = 0) -> None:
        """Merge data into a tomlkit table in place, keeping comments."""
        for key in [k for k in table if k not in data]:
            del table[key]
        for key, value in data.items():
            if not isinstance(value, dict):
                table[key] = value
            elif isinstance(table.get(key), dict):
                cls._update(table[key], value, depth + 1)
            elif depth >= cls.dotted_key_depth:
                for path, leaf in cls._leaves(value):
                    table.add(tomlkit.key([key, *path]), leaf)
            else:
                new_table = tomlkit.table(is_super_table=depth == 0)
                cls._update(new_table, value, depth + 1)
                table[key] = new_table

    @classmethod
    def _leaves(
        cls, data: dict[str, Any], path: tuple[str, ...] = ()
    ) -> Iterator[tuple[tuple[str, ...], Any]]:
        for key, value in data.items():
            if isinstance(value, dict):
                yield from cls._leaves(value, (*path, key))
            else:
                yield (*path, key), value


class ConfigFile(ConfigModel):
    """A model stored as a TOML file."""

    _path: Path | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        super().model_post_init(context)
        # Always save top-level fields, even if only changed in place
        self.model_fields_set.update(type(self).model_fields)

    @classmethod
    def default_path(cls) -> Path | None:
        """Where this file is stored if no path is given, if anywhere."""
        return None

    @classmethod
    def _resolve_path(cls, path: Path | None) -> Path:
        if (path := path or cls.default_path()) is None:
            raise ValueError(f"No path for {cls.__name__}")
        return path

    @property
    def path(self) -> Path:
        """Where this file is loaded from and saved to."""
        return self._path or self._resolve_path(None)

    @classmethod
    def load(
        cls, path: Path | None = None, *, missing_ok: bool = False
    ) -> Self:
        """Load from `path`, or from the default path.

        With `missing_ok`, a missing file loads as an empty instance, which is
        saved to that path.
        """
        path = cls._resolve_path(path)
        try:
            with path.open("r") as f:
                data = tomlkit.load(f).unwrap()
        except FileNotFoundError:
            if not missing_ok:
                raise
            instance = cls()
            instance._path = path
            return instance
        cls._restrict_permissions(path)
        instance = cls.model_validate(data)
        instance._path = path  # noqa: SLF001
        return instance

    @classmethod
    def _restrict_permissions(cls, path: Path) -> None:
        mode = stat.S_IMODE(path.stat().st_mode)
        if os.name != "posix" or not mode & 0o077:
            return
        new_mode = mode & 0o700
        try:
            path.chmod(new_mode)
        except OSError as e:
            message = "Failed to correct %s permissions from %04o to %04o: %s"
            log.warning(message, path, mode, new_mode, e)
            return
        log.warning(
            "Corrected %s permissions from %04o to %04o", path, mode, new_mode
        )

    def delete(self, *, missing_ok: bool = False) -> None:
        self.path.unlink(missing_ok=missing_ok)

    def save(self, path: Path | None = None) -> None:
        """Write to `path`, or to this file's path."""
        path = path or self.path
        data = tomlkit.parse(path.read_text()) if path.is_file() else None
        data = data or tomlkit.document()
        self._update(
            data,
            self.model_dump(
                mode="json",
                by_alias=True,
                exclude_unset=True,
                exclude_none=True,
            ),
        )
        dirs.mkdirs(path.parent)
        with tempfile.TemporaryDirectory(dir=path.parent, suffix=".tmp") as td:
            temp_path = Path(td) / f".{path.name}.tmp"
            with temp_path.open("w") as file:
                temp_path.chmod(0o600)
                tomlkit.dump(data, file)
            temp_path.replace(path)
        self._path = path
