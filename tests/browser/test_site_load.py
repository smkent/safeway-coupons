from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest
from patchright.sync_api import Error as PlaywrightError
from patchright.sync_api import Page

from safeway_coupons.brands import Brand

if TYPE_CHECKING:
    from pathlib import Path

    from patchright.sync_api import Response

    from tests.utils import CapLogHelper, MainRunner, MockMail

    from .conftest import MockSite


SITE_URL = f"{Brand.Safeway.origin}/"


@pytest.mark.usefixtures("accounts_toml")
def test_site_load_failure_emails_screenshot(
    main_runner: MainRunner, mail: MockMail, mock_site: MockSite
) -> None:
    main_runner(match=1)
    assert mock_site.requests
    assert len(mail.messages) == 1
    assert mail.screenshot(mail.messages[0]).startswith(b"\x89PNG")


@pytest.mark.parametrize(
    ("brand", "site_url"),
    [
        pytest.param(None, "https://www.safeway.com/", id="default"),
        pytest.param(
            "albertsons", "https://www.albertsons.com/", id="albertsons"
        ),
    ],
)
def test_site_load_failure_logs_failed_requests(
    main_runner: MainRunner,
    accounts_toml: Path,
    caplog_helper: CapLogHelper,
    mock_site: MockSite,
    brand: str | None,
    site_url: str,
) -> None:
    if brand:
        accounts_toml.write_text(
            accounts_toml.read_text().replace(
                "[accounts.ness]", f'[accounts.ness]\nbrand = "{brand}"', 1
            )
        )
    main_runner("-a", "ness", "--verbose", match=1)
    records = caplog_helper.match_records("Request failed")
    assert all(r.levelno == logging.DEBUG for r in records)
    assert caplog_helper.match_records(
        f" document   GET  {site_url} (net::ERR_FAILED)"
    )
    assert mock_site.requests[0] == site_url


@pytest.mark.usefixtures("accounts_toml")
def test_site_load_failure_logs_pending_requests(
    main_runner: MainRunner,
    caplog_helper: CapLogHelper,
    mock_site: MockSite,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_url = f"{SITE_URL}zombocom.png"
    # Serve a home page with an image that never loads
    mock_site.handlers[SITE_URL] = lambda route: route.fulfill(
        content_type="text/html", body=f'<img src="{image_url}">'
    )
    mock_site.handlers[image_url] = lambda _: None
    real_goto = Page.goto

    def goto(self: Page, url: str, **kwargs: Any) -> Response | None:
        if url != SITE_URL:
            return real_goto(self, url, **kwargs)
        # Load the home page without waiting for the image, then fail
        with (
            self.expect_event("requestfinished", lambda r: r.url == url),
            self.expect_request(image_url),
        ):
            real_goto(self, url, wait_until="commit")
        raise PlaywrightError("Navigation failed")

    monkeypatch.setattr(Page, "goto", goto)
    main_runner("--verbose", match=1)
    [record] = caplog_helper.match_records("page requests were still pending")
    assert record.levelno == logging.DEBUG
    _, *pending = record.getMessage().splitlines()
    assert [line.split()[1:] for line in pending] == [
        ["image", "GET", image_url]
    ]
