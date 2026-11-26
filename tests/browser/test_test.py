from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.utils import CapLogHelper, MainRunner


def test_verify_browser(
    main_runner: MainRunner, caplog_helper: CapLogHelper
) -> None:
    main_runner("browser", "test")
    [record] = caplog_helper.match_records("Browser version: ")
    assert re.match(r"^\d+(\.\d+){3}$", record.message.split()[-1])
