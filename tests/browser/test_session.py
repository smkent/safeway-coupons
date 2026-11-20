from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from tests.utils import MainRunner, MockMail

    from .conftest import MockSite


def test_site_load_failure_emails_screenshot(
    main_runner: MainRunner,
    accounts_config: Path,
    mail: MockMail,
    mock_site: MockSite,
) -> None:
    main_runner("-c", str(accounts_config), match=1)
    assert mock_site.requests
    assert len(mail.messages) == 1
    assert mail.screenshot(mail.messages[0]).startswith(b"\x89PNG")
