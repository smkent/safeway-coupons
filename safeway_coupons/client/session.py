from __future__ import annotations

import itertools
import json
import logging
import re
import sys
import tempfile
import time
import urllib
import urllib.parse
from abc import ABC, abstractmethod
from contextlib import ExitStack, contextmanager, nullcontext, suppress
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self

from patchright.sync_api import TimeoutError as PlaywrightTimeoutError
from patchright.sync_api import sync_playwright

from safeway_coupons.console import LogLevel, log
from safeway_coupons.dirs import DirsMixin
from safeway_coupons.errors import (
    AuthenticationFailure,
    BrowserSessionError,
    MultiFactorAuthenticationRequired,
    NotSignedIn,
)
from safeway_coupons.models.safeway.auth import AuthErrorResponse, AuthResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

    from patchright.sync_api import (
        BrowserContext,
        Cookie,
        Frame,
        Locator,
        Page,
        Playwright,
        Request,
        Response,
    )

    from safeway_coupons.account import Account


SITE_URL = "https://www.safeway.com/"


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

        def _format_request(
            request: Request, duration: float | None = None
        ) -> str:
            duration_str = "unknown"
            if duration is not None:
                duration_str = _duration_str(duration)
            return (
                f"{duration_str:>6}"
                f" {request.resource_type:<10}"
                f" {request.method:<4} {_loggable_url(request.url)}"
            )

        def _log(request: Request, start_time: float | None = None) -> None:
            failure = request.failure
            level = logging.DEBUG if failure else LogLevel.TRACE
            if not log.isEnabledFor(level):
                return
            verb = "failed" if failure else "finished"
            failure_str = f" ({failure})" if failure else ""
            duration = None
            if start_time is not None:
                duration = time.monotonic() - start_time
            log.log(
                level,
                "Request %-9s %s%s",
                f"{verb}:",
                _format_request(request, duration),
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
                "  " + _format_request(request, now - started)
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


@dataclass
class SafewayBrowserSession(BrowserSession):
    account: Account

    STATE_FILE_BASE: ClassVar[dict[str, Any]] = {"_version": 1}
    # Non-blank greeting not starting with "Sign in", ignoring leading symbols
    SIGNED_IN_GREETING = re.compile(r"^(?!\W*sign in\b)\s*\S", re.IGNORECASE)

    def __post_init__(self) -> None:
        super().__post_init__()

    def __enter__(self) -> Self:
        @contextmanager
        def _cleanup_on_error() -> Generator[None]:
            with ExitStack() as stack:
                stack.push(self)
                yield
                stack.pop_all()

        super().__enter__()
        with _cleanup_on_error():
            self.load_site_home()
        return self

    def load_site_home(self) -> None:
        self.page.goto(SITE_URL)
        # Wait out any initial reloads by waiting for the account button
        self._account_button.wait_for(state="attached")
        self.page.wait_for_load_state("load")

    @cached_property
    def state_subdir(self) -> Path:
        return self.account.state_subdir / f"browser-{self.channel.lower()}"

    @property
    def state(self) -> dict[str, Any]:
        state_file = self.state_dir / "state.json"
        if not state_file.is_file():
            return self.STATE_FILE_BASE.copy()
        return json.loads(state_file.read_text())

    @state.setter
    def state(self, value: dict[str, Any]) -> None:
        new_value = self.STATE_FILE_BASE | value
        state_file = self.place_state_file("state.json")
        with tempfile.TemporaryDirectory(dir=state_file.parent) as td:
            tf = Path(td) / state_file.name
            with tf.open("w") as file:
                json.dump(new_value, fp=file, indent=4)
            tf.replace(state_file)
        log.debug("Wrote state file: %s", state_file)

    @cached_property
    def page(self) -> Page:
        page = super().page

        def log_navigation(frame: Frame) -> None:
            if frame == self.page.main_frame:
                log.debug("Navigated: %s", frame.url)

        page.on("framenavigated", log_navigation)

        def log_api_response(response: Response) -> None:
            if response.request.resource_type not in {"xhr", "fetch"}:
                return
            url = urllib.parse.urlsplit(response.url)
            if not re.search(r"safeway\.com|albertsons|okta|ciam", url.netloc):
                return
            log.debug(
                "Response: %d %s %s%s",
                response.status,
                response.request.method,
                url.netloc,
                url.path,
            )

        page.on("response", log_api_response)

        def dismiss_cookie_banner(banner: Locator) -> None:
            log.info("Dismissing cookie banner")
            self._click_to_reload(
                banner.get_by_role(
                    "button", name=re.compile("necessary only", re.IGNORECASE)
                )
            )

        page.add_locator_handler(
            page.get_by_role("region", name="Cookie banner"),
            dismiss_cookie_banner,
        )

        def dismiss_info_modal(modal: Locator) -> None:
            log.info("Dismissing personal info confirmation modal")
            self._click_to_reload(
                modal.get_by_role(
                    "button", name=re.compile(r"^close$", re.IGNORECASE)
                )
            )

        page.add_locator_handler(
            page.get_by_role("dialog", name="Verify 180 Days Modal"),
            dismiss_info_modal,
        )

        return page

    def _click_to_reload(self, button: Locator) -> None:
        with (
            ExitStack() as stack,
            self.page.expect_navigation(wait_until="commit", timeout=10000),
        ):
            button.click(no_wait_after=True)
            # Preserve click failures but prevent navigation timeouts from
            # stopping a triggering handler
            stack.enter_context(suppress(PlaywrightTimeoutError))

    @property
    def _account_button(self) -> Locator:
        return self.page.get_by_role(
            "button", name=re.compile(r"^account menu$", re.IGNORECASE)
        )

    def is_signed_in(self, *, check: bool = False) -> bool:
        greeting = self._account_button.locator(".user-greeting")
        greeting.wait_for()
        self.page.wait_for_load_state("load")
        if check and "SWY_SHARED_SESSION" not in self.cookies:
            log.debug("No existing session cookie found")
            return False
        signed_in = greeting.filter(has_text=self.SIGNED_IN_GREETING)
        with suppress(PlaywrightTimeoutError):
            signed_in.wait_for(timeout=self.DEFAULT_TIMEOUT)
        return bool(signed_in.count())

    def open_sign_in_modal(self) -> Locator | None:
        if not (panel := self.open_sign_in_panel()):
            return None
        panel.get_by_role(
            "button", name=re.compile(r"^sign in$", re.IGNORECASE)
        ).click()
        modal = self.page.get_by_role("dialog", name="Sign in modal")
        modal.wait_for()
        log.info("Sign in modal open")
        return modal

    def open_sign_in_panel(self, timeout: float = 120) -> Locator | None:
        panel = self.page.get_by_role(
            "dialog", name=re.compile("account menu", re.IGNORECASE)
        )
        signed_in_menu = self.page.locator(".myaccount-flyout-wrapper")
        # Both menus are in the page, but only the open one is visible
        open_menu = panel.or_(signed_in_menu).filter(visible=True)
        deadline = time.monotonic() + timeout
        for attempt in itertools.count(1):
            # Clicking again while a menu is open would be blocked by it
            if not open_menu.count():
                self._account_button.click()
            try:
                open_menu.first.wait_for(
                    timeout=min(10000 * attempt, (timeout * 1000) / 4)
                )
            except PlaywrightTimeoutError:
                if time.monotonic() >= deadline:
                    break
                log.info(
                    "Sign in panel didn't open, reloading page (attempt %d)",
                    attempt + 1,
                )
                self.load_site_home()
                continue
            if signed_in_menu.is_visible():
                log.debug("Account menu shows a signed in user")
                return None
            log.debug("Sign in panel open after attempt %d", attempt)
            return panel
        msg = f"Sign in panel did not open after {attempt} attempts"
        raise RuntimeError(msg)

    def restore_saved_device_id(self) -> None:
        try:
            cookie = self.cookies["SWY_SHARED_SESSION_INFO"]
            session_info = self.cookie_to_json(cookie)
        except (KeyError, ValueError):
            return
        if not (device_id := self.state.get("device_id")):
            return
        session_info.setdefault("info", {}).setdefault("COMMON", {})[
            "deviceId"
        ] = device_id
        self.cookie_from_json(cookie, session_info)
        self.page.context.add_cookies([{**cookie}])

    def sign_in(self, *, check: bool = False) -> None:
        if self.is_signed_in(check=True):
            log.info("Already signed in")
            return
        if check:
            raise NotSignedIn(self.account)
        self.restore_saved_device_id()
        if modal := self.open_sign_in_modal():
            modal.get_by_role("textbox", name="Email or mobile number").fill(
                self.account.username
            )
            modal.get_by_role("button", name="Sign in with password").click()
            log.info("Clicked Sign in with password")
            if self.account.password:
                self.submit_password(modal, self.account.password)
        if not self.is_signed_in():
            raise RuntimeError("Sign in did not complete")
        log.info("Signed in")

    def submit_password(self, modal: Locator, password: str) -> None:
        modal.get_by_role("textbox", name="Password").fill(password)
        with self.page.expect_response(
            lambda r: urllib.parse.urlsplit(r.url).path.endswith(
                "/csms/authn/factors/password/verify"
            )
        ) as verify:
            modal.get_by_role(
                "button", name=re.compile(r"^sign in$", re.IGNORECASE)
            ).click(no_wait_after=True)
        log.info("Clicked Sign in")
        if (destination := self.verification_required(verify.value)) is None:
            return
        log.info("Safeway requires device verification (%s)", destination)
        if not self.headless:
            input(
                "Complete device verification in the browser window,"
                " then press Enter here to continue: "
            )
            if not self.is_signed_in():
                raise RuntimeError(
                    f"Device verification ({destination}) was not completed"
                )
            return
        # Check before sending a code that nobody is there to enter
        if not sys.stdin.isatty():
            raise MultiFactorAuthenticationRequired(self.account)
        self.verify_device(modal)

    def verify_device(self, modal: Locator, attempts: int = 3) -> None:
        def _factor_action(action: str) -> Callable[[Response], bool]:
            pattern = re.compile(rf"/csms/authn/factors/[^/]+/{action}$")
            return lambda r: bool(
                pattern.search(urllib.parse.urlsplit(r.url).path)
            )

        if (radios := modal.get_by_role("radio")).count():
            option = radios.first.locator("xpath=ancestor::label[1]")
            option.click()
            log.info("Verifying with: %s", option.inner_text().strip())
        with self.page.expect_response(_factor_action("send")) as send:
            modal.get_by_role(
                "button", name=re.compile(r"^continue$", re.IGNORECASE)
            ).click()
        if not send.value.ok:
            raise RuntimeError(
                f"Sending verification code failed ({send.value.status})"
            )
        code_box = modal.get_by_role("textbox", name="Enter Verification Code")
        code_box.wait_for()
        tries = 0
        while tries < attempts:
            code = input(
                "Enter the verification code (blank to cancel): "
            ).strip()
            if not code:
                raise RuntimeError("Device verification cancelled")
            if not re.fullmatch(r"\d{6}", code):
                log.info("The verification code is 6 digits")
                continue
            tries += 1
            code_box.fill(code)
            with self.page.expect_response(_factor_action("verify")) as verify:
                modal.get_by_role(
                    "button", name=re.compile(r"^sign in$", re.IGNORECASE)
                ).click(no_wait_after=True)
            if verify.value.ok:
                log.info("Device verified")
                return
            log.error(
                "Verification code not accepted (%s)",
                self.error_message(verify.value),
            )
        raise RuntimeError(
            f"Verification code not accepted after {attempts} attempts"
        )

    @staticmethod
    def error_message(response: Response) -> str:
        try:
            body = AuthErrorResponse.model_validate(response.json())
        except Exception:  # noqa: BLE001
            body = AuthErrorResponse()
        return next(
            (e.message for e in body.errors if e.message),
            f"HTTP {response.status}",
        )

    @staticmethod
    def verification_required(response: Response) -> str | None:
        try:
            body = AuthResponse.model_validate(response.json())
        except Exception:  # noqa: BLE001
            # A successful sign in can reload the page before this is read
            return None
        if not body.mfa_required:
            return None
        return ", ".join(f.destination for f in body.factors)


@dataclass
class LoginSession:
    account: Account
    access_token: str | None = field(default=None, init=False)
    store_id: str | None = field(default=None, init=False)
    user_agent: str | None = field(default=None, init=False)
    headless: bool = field(default=True, kw_only=True)
    dry_run: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        try:
            self._login()
        except AuthenticationFailure:
            raise
        except BrowserSessionError as e:
            # Pass on specific failures, such as a verification code being
            # needed, with the browser session's screenshot
            if isinstance(e.__cause__, AuthenticationFailure):
                e.__cause__.attachments = e.attachments
                raise e.__cause__ from None
            raise AuthenticationFailure(
                self.account, attachments=e.attachments
            ) from e
        except Exception as e:
            raise AuthenticationFailure(self.account) from e

    def _login(self) -> None:
        with SafewayBrowserSession(
            account=self.account, headless=self.headless
        ) as browser:
            self.user_agent = browser.user_agent
            log.debug("User Agent: %s", self.user_agent)

            browser.sign_in(check=self.dry_run)

            log.info("Retrieve session information")
            session_cookie = browser.cookie_to_json(
                browser.cookies["SWY_SHARED_SESSION"]
            )
            self.access_token = session_cookie["accessToken"]
            session_info = browser.cookie_to_json(
                browser.cookies["SWY_SHARED_SESSION_INFO"]
            )
            device_id = (
                session_info.get("info", {}).get("COMMON", {}).get("deviceId")
            )
            log.debug("Device ID: %s", device_id)
            if device_id and not browser.state.get("device_id"):
                browser.state |= {"device_id": device_id}
            if not (store_id := session_info["info"]["J4U"]["storeId"]):
                raise ValueError("Unable to retrieve store ID")
            self.store_id = store_id

            if not self.headless:
                input(
                    "Complete any interaction in the browser window,"
                    " then press Enter here to continue: "
                )
