from __future__ import annotations

import json
import logging
import re
import time
import urllib
import urllib.parse
from abc import ABC, abstractmethod
from contextlib import ExitStack, contextmanager, nullcontext, suppress
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

from patchright.sync_api import sync_playwright

from .console import LogLevel, log
from .dirs import DirsMixin
from .errors import BrowserSessionError

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from patchright.sync_api import (
        BrowserContext,
        Cookie,
        Page,
        Playwright,
        Request,
    )


@dataclass
class BrowserSession(ExitStack, DirsMixin, ABC):
    DEFAULT_TIMEOUT = 60 * 1000
    MAX_PENDING_REQUESTS_LOGGED = 20

    channel: str = field(default="chrome", kw_only=True)
    headless: bool = field(default=True, kw_only=True)
    screen: str | None = field(default="1920x1080", kw_only=True)

    def __post_init__(self) -> None:
        super().__init__()

    @property
    @abstractmethod
    def state_subdir(self) -> Path: ...

    @cached_property
    def user_agent(self) -> str:
        return self.page.evaluate("navigator.userAgent")

    @property
    def cookies(self) -> Mapping[str, Cookie]:
        return {c["name"]: c for c in self.page.context.cookies()}

    def cookie_to_json(self, cookie: Cookie) -> dict[str, Any]:
        return json.loads(urllib.parse.unquote(cookie["value"]))

    def cookie_from_json(self, cookie: Cookie, value: dict[str, Any]) -> None:
        cookie["value"] = urllib.parse.quote(
            json.dumps(value, separators=(",", ":")), safe="!~*'()"
        )

    @cached_property
    def configured_profile_dir(self) -> Path:
        profile_subdir = Path("profile")
        dd = self.place_state_file(profile_subdir)
        prefs_path = self.place_state_file(
            profile_subdir / Path("Default") / "Preferences"
        )
        prefs = (
            json.loads(prefs_path.read_text()) if prefs_path.is_file() else {}
        )
        # Show new tab page on startup
        prefs.setdefault("session", {})["restore_on_startup"] = 5
        # Don't offer to restore crashed sessions
        prefs.setdefault("profile", {})["exit_type"] = "Normal"
        prefs_path.write_text(json.dumps(prefs))
        # Remove any stale lock files
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            (dd / name).unlink(missing_ok=True)
        log.info("Browser profile dir (user_data_dir): %s", dd)
        return dd

    @cached_property
    def browser_context(self) -> BrowserContext:
        log.info("Starting browser session")
        p = self.enter_context(sync_playwright())
        args = ["--window-size=1366,900"]
        if self.screen:
            args.append(f"--screen-info={{{self.screen}}}")
        if user_agent := self._user_agent_override(p):
            args.append(f"--user-agent={user_agent}")
        context = self.enter_context(
            p.chromium.launch_persistent_context(
                user_data_dir=self.configured_profile_dir,
                channel=self.channel,
                headless=self.headless,
                no_viewport=True,
                args=args,
            )
        )
        # Allow for slow hardware in all actions, waits and navigations
        context.set_default_timeout(self.DEFAULT_TIMEOUT)
        return context

    @cached_property
    def single_page(self) -> Page:
        ctx = self.browser_context
        self.enter_context(nullcontext() if ctx.pages else ctx.new_page())
        page, *extra_tabs = ctx.pages
        for extra_tab in extra_tabs:
            extra_tab.close()
        self._check_user_agent(page)
        log.info("Browser session ready")
        return page

    @cached_property
    def page(self) -> Page:
        return self.enter_context(self._new_page())

    @contextmanager
    def _new_page(self) -> Generator[Page]:
        page = self.single_page
        try:
            with self._track_pending_requests(page):
                yield page
        except Exception as e:
            attachments = []
            screenshot_path = self.place_state_file(
                Path("debug") / "screenshot.png"
            )
            with suppress(Exception):
                page.screenshot(path=screenshot_path)
                log.info("Screenshot saved: %s", screenshot_path)
            if screenshot_path.is_file():
                attachments.append(screenshot_path)
            raise BrowserSessionError(attachments=attachments) from e

    @contextmanager
    def _track_pending_requests(self, page: Page) -> Generator[None]:  # noqa: C901
        pending_requests: dict[Request, float] = {}

        def _loggable_url(url: str, max_length: int = 200) -> str:
            parts = urllib.parse.urlparse(url)
            short = urllib.parse.urlunparse((*parts[:3], "", "", ""))
            if len(short) > max_length:
                short = short[: max_length - 3] + "..."
            return short

        def _duration_str(duration: float) -> str:
            if duration < 1:
                return f"{int(duration * 1000)}ms"
            return f"{duration:.1f}s"

        def _log(request: Request, start_time: float | None = None) -> None:
            failure = request.failure
            level = logging.DEBUG if failure else LogLevel.TRACE
            if not log.isEnabledFor(level):
                return
            duration_str = ""
            if start_time is not None:
                duration_str = _duration_str(time.monotonic() - start_time)
            verb = "failed" if failure else "finished"
            failure_str = f" ({failure})" if failure else ""
            log.log(
                level,
                "Request %-9s %8s %-10s %-4s %s%s",
                f"{verb}:",
                duration_str,
                request.resource_type,
                request.method,
                _loggable_url(request.url),
                failure_str,
            )

        def _started(request: Request) -> None:
            pending_requests[request] = time.monotonic()

        def _finished(request: Request) -> None:
            _log(request, start_time=pending_requests.pop(request, None))

        def _log_pending_requests() -> None:
            if not pending_requests or not log.isEnabledFor(logging.DEBUG):
                return
            now = time.monotonic()
            oldest = sorted(pending_requests.items(), key=lambda item: item[1])
            lines = [
                f"  {_duration_str(now - started):>6}"
                f" {request.resource_type:<10}"
                f" {request.method:<4} {_loggable_url(request.url)}"
                for request, started in oldest[
                    : self.MAX_PENDING_REQUESTS_LOGGED
                ]
            ]
            if (more := len(oldest) - len(lines)) > 0:
                lines.append(f"  ... and {more} more")
            log.debug(
                "%d page requests were still pending (oldest first):\n%s",
                len(oldest),
                "\n".join(lines),
            )

        page.on("request", _started)
        page.on("requestfinished", _finished)
        page.on("requestfailed", _finished)
        try:
            yield
        except Exception:
            _log_pending_requests()
            raise
        finally:
            page.remove_listener("request", _started)
            page.remove_listener("requestfinished", _finished)
            page.remove_listener("requestfailed", _finished)

    def _user_agent_override(self, p: Playwright) -> str | None:
        if not self.headless:
            return None
        browser = p.chromium.launch(channel=self.channel, headless=True)
        try:
            cdp = browser.new_browser_cdp_session()
            user_agent = cdp.send("Browser.getVersion")["userAgent"]
        finally:
            browser.close()
        if "HeadlessChrome" not in user_agent:
            return None
        fixed = user_agent.replace("HeadlessChrome", "Chrome")
        log.debug("Overriding user agent: %s", fixed)
        return fixed

    @staticmethod
    def _check_user_agent(page: Page) -> None:
        """Ensure user agent and client hints match."""
        url = "https://user-agent-check.invalid/"
        page.route(url, lambda route: route.fulfill(body="<html></html>"))
        try:
            page.goto(url)
            user_agent = page.evaluate("navigator.userAgent")
            brands = {
                b["brand"]: b["version"]
                for b in page.evaluate("navigator.userAgentData.brands")
            }
        finally:
            page.unroute(url)
            page.goto("about:blank")
        browser = next(
            (b for b in ("Google Chrome", "Chromium") if b in brands), None
        )
        match = re.search(r"\bChrome/(\d+)\.", user_agent)
        if (
            "Headless" in user_agent
            or browser is None
            or match is None
            or match.group(1) != brands[browser]
        ):
            raise RuntimeError(
                "User agent doesn't match client hints:"
                f" {user_agent!r} vs {brands!r}"
            )
