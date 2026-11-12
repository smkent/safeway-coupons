from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.conftest import MainRunner


def test_main_help(main_runner: MainRunner) -> None:
    main_runner("--help")
