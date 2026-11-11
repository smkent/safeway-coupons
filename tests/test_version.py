from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

import safeway_coupons
from safeway_coupons.__main__ import version

if TYPE_CHECKING:
    from collections.abc import Generator

    from .conftest import MainRunner


def test_version() -> None:
    assert safeway_coupons.version


@pytest.fixture
def version_output(capsys: pytest.CaptureFixture[str]) -> Generator[None]:
    yield None
    capture_result = capsys.readouterr()
    assert capture_result.out == safeway_coupons.version + os.linesep
    assert capture_result.err == ""


@pytest.mark.usefixtures("version_output")
@pytest.mark.parametrize("cli_option", ["version", "--version", "-V"])
def test_version_main(main_runner: MainRunner, cli_option: str) -> None:
    main_runner(cli_option)


@pytest.mark.usefixtures("version_output")
def test_version_function() -> None:
    version()
