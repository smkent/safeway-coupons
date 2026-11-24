from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest
    from syrupy.assertion import SnapshotAssertion

    from tests.utils import MainRunner


@dataclass
class ExpectedOutput:
    stdout: str = ""
    stderr: str = ""
    logs: Sequence[str] | None = None


@dataclass
class OutputTest:
    capsys: pytest.CaptureFixture[str]
    caplog: pytest.LogCaptureFixture
    snapshot: SnapshotAssertion
    main_runner: MainRunner
    expected: ExpectedOutput | None = None

    def __call__(self, *cmd: str, match: int = 0) -> None:
        self.main_runner(*cmd, match=match)

    def check(self) -> None:
        capture_result = self.capsys.readouterr()
        if self.expected:
            assert capture_result.out == self.expected.stdout
            if self.expected.logs is None:
                assert capture_result.err == self.expected.stderr
            else:
                assert [
                    r.getMessage() for r in self.caplog.get_records("call")
                ] == list(self.expected.logs)
        else:
            assert capture_result.out == self.snapshot
            assert capture_result.err == self.snapshot
