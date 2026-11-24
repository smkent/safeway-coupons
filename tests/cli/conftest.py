from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .utils import OutputTest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from syrupy.assertion import SnapshotAssertion

    from tests.utils import MainRunner


@pytest.fixture
def output_test(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
    main_runner: MainRunner,
) -> Iterator[OutputTest]:
    out = OutputTest(
        capsys=capsys,
        caplog=caplog,
        snapshot=snapshot,
        main_runner=main_runner,
    )
    yield out
    out.check()
