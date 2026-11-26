from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from safeway_coupons.browser import BrowserSession
from safeway_coupons.console import log
from safeway_coupons.dirs import APP_NAME
from safeway_coupons.errors import BrowserSessionError

from .cli import CLI

if TYPE_CHECKING:
    from patchright.sync_api import CDPSession

cli = CLI(
    name="browser",
    help="Manage browser integration",
    hidden=True,
    invoke_without_command=False,
    no_args_is_help=True,
)


@cli.command()
def test() -> None:
    """Start the browser with a test page and log the browser version."""

    @dataclass
    class TemporaryBrowserSession(BrowserSession):
        state_path: Path = field(init=False, kw_only=True)

        def __post_init__(self) -> None:
            super().__post_init__()
            dir_ctx = TemporaryDirectory(prefix=f"{APP_NAME}.browser-test.")
            self.state_path = Path(self.enter_context(dir_ctx))

        @cached_property
        def state_subdir(self) -> Path:
            return self.state_path

        @cached_property
        def cdp(self) -> CDPSession:
            return self.browser_context.new_cdp_session(self.page)

        @cached_property
        def browser_version(self) -> str:
            version_data = self.cdp.send("Browser.getVersion")
            return version_data["product"].rpartition("/")[2]

    with TemporaryBrowserSession() as session:
        session.page.set_content('<p id="z">Bacon ipsum</p>')
        if (text := session.page.locator("#z").inner_text()) != "Bacon ipsum":
            raise BrowserSessionError(
                message=f"Unexpected page content: {text!r}"
            )
        log.info("Browser version: %s", session.browser_version)
