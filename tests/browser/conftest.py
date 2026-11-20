from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from patchright.sync_api import BrowserType

if TYPE_CHECKING:
    from patchright.sync_api import BrowserContext, Route

SITE_URL = "https://www.safeway.com/"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply the browser marker to all tests in this directory."""
    this_dir = Path(__file__).parent
    for item in items:
        if item.path and item.path.is_relative_to(this_dir):
            item.add_marker(pytest.mark.browser)


@pytest.fixture
def mock_browser_driver() -> None:
    """Use the real browser driver in browser tests."""


@dataclass
class MockSite:
    requests: list[str] = field(default_factory=list)

    def request_route(self, route: Route) -> None:
        try:
            if (url := route.request.url).startswith(SITE_URL):
                self.requests.append(url)
        finally:
            route.abort()


@pytest.fixture
def mock_site(monkeypatch: pytest.MonkeyPatch) -> MockSite:
    site = MockSite()
    real_launch = BrowserType.launch_persistent_context

    def launch_with_mock_site(
        self: BrowserType, *args: Any, **kwargs: Any
    ) -> BrowserContext:
        context = real_launch(self, *args, **kwargs)
        context.route("**/*", site.request_route)
        return context

    monkeypatch.setattr(
        BrowserType, "launch_persistent_context", launch_with_mock_site
    )
    return site
