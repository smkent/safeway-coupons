from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.utils import MockDirs

from .utils import ExpectedOutput

if TYPE_CHECKING:
    from .utils import OutputTest


@pytest.fixture(params=MockDirs.Type.params())
def mock_dirs_type(request: pytest.FixtureRequest) -> MockDirs.Type:
    return request.param


@pytest.mark.parametrize("command", ["list", "ls"])
def test_storage_list(
    output_test: OutputTest, mock_dirs: MockDirs, command: str
) -> None:
    output_test.expected = ExpectedOutput(
        stdout=f"Config: {mock_dirs.config}\nState: {mock_dirs.state}\n"
    )
    output_test("storage", command)


@pytest.mark.parametrize("name", ["config", "state"])
def test_storage_show(
    output_test: OutputTest, mock_dirs: MockDirs, name: str
) -> None:
    path = getattr(mock_dirs, name)
    output_test.expected = ExpectedOutput(stdout=f"{path}\n")
    output_test("storage", "show", name)
