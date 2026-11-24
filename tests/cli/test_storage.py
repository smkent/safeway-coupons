from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from tests.utils import MockDirs

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.utils import MainRunner


@pytest.fixture(params=MockDirs.Type.params())
def mock_dirs_type(request: pytest.FixtureRequest) -> MockDirs.Type:
    return request.param


@dataclass
class OutputTest:
    capsys: pytest.CaptureFixture[str]
    main_runner: MainRunner
    stdout: str = ""
    stderr: str = ""

    def __call__(self, *cmd: str, match: int = 0) -> None:
        self.main_runner(*cmd, match=match)


@pytest.fixture
def output_test(
    capsys: pytest.CaptureFixture[str], main_runner: MainRunner
) -> Iterator[OutputTest]:
    out = OutputTest(capsys=capsys, main_runner=main_runner)
    yield out
    capture_result = capsys.readouterr()
    assert capture_result.out == out.stdout
    assert capture_result.err == out.stderr


@pytest.mark.parametrize("command", ["list", "ls"])
def test_storage_list(
    output_test: OutputTest, mock_dirs: MockDirs, command: str
) -> None:
    output_test.stdout = f"State: {mock_dirs.state}\n"
    output_test("storage", command)


@pytest.mark.parametrize("name", ["state"])
def test_storage_show(
    output_test: OutputTest, mock_dirs: MockDirs, name: str
) -> None:
    path = getattr(mock_dirs, name)
    output_test.stdout = f"{path}\n"
    output_test("storage", "show", name)
