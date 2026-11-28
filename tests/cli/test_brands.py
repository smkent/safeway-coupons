from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .utils import OutputTest


@pytest.fixture(params=["brand", "brands"])
def brands_command(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.mark.parametrize("command", ["list", "ls"])
def test_brands_list(
    output_test: OutputTest, brands_command: str, command: str
) -> None:
    output_test(brands_command, command)
