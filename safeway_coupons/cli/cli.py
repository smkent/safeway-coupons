from __future__ import annotations

import os
import shutil
from typing import Any

from typer import Typer
from typer.core import TyperGroup


class CLI(Typer):
    class SortedCommands(TyperGroup):
        def list_commands(self, *_: Any, **__: Any) -> list[str]:
            return sorted(self.commands)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("add_completion", False)
        kwargs.setdefault("pretty_exceptions_enable", False)
        kwargs.setdefault("cls", self.SortedCommands)
        super().__init__(*args, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self._setup_env()
        super().__call__(*args, **kwargs)

    def _setup_env(self) -> None:
        os.environ.setdefault(
            "TERMINAL_WIDTH", str(min(shutil.get_terminal_size().columns, 160))
        )
