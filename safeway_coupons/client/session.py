from __future__ import annotations

import itertools
import json
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
        Cookie,
        Frame,
        Locator,
        Page,
        Playwright,
        Response,
    )

    from safeway_coupons.account import Account


@dataclass
class BrowserSession(ExitStack, DirsMixin, ABC):
    DEFAULT_TIMEOUT = 60 * 1000

    channel: str = field(default="chrome", kw_only=True)
    headless: bool = field(default=True, kw_only=True)
    screen: str | None = field(default="1920x1080", kw_only=True)
    debug_level: int = field(default=0, kw_only=True)

    def __post_init__(self) -> None:
        super().__init__()

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
    def page(self) -> Page:
        return self.enter_context(self._new_page())

    @property
    @abstractmethod
    def state_subdir(self) -> Path: ...

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
        print(f"Browser profile dir (user_data_dir): {dd}")  # noqa: T201
        return dd

    @contextmanager
    def _new_page(self) -> Generator[Page]:
        print("Starting browser session")  # noqa: T201
        with sync_playwright() as p:
            args = ["--window-size=1366,900"]
            if self.screen:
                args.append(f"--screen-info={{{self.screen}}}")
            if user_agent := self._user_agent_override(p):
                args.append(f"--user-agent={user_agent}")
            with (
                p.chromium.launch_persistent_context(
                    user_data_dir=self.configured_profile_dir,
                    channel=self.channel,
                    headless=self.headless,
                    no_viewport=True,
                    args=args,
                ) as ctx,
                nullcontext() if ctx.pages else ctx.new_page(),
            ):
                # Allow for slow hardware in all actions, waits and navigations
                ctx.set_default_timeout(self.DEFAULT_TIMEOUT)
                page, *extra_tabs = ctx.pages
                for extra_tab in extra_tabs:
                    extra_tab.close()
                page.wait_for_timeout(500)
                self._check_user_agent(page)
                print("Browser session ready")  # noqa: T201
                try:
                    yield page
                except Exception as e:
                    attachments = []
                    screenshot_path = self.place_state_file(
                        Path("debug") / "screenshot.png"
                    )
                    with suppress(Exception):
                        page.screenshot(path=screenshot_path)
                        print(f"Screenshot saved: {screenshot_path}")  # noqa: T201
                    if screenshot_path.is_file():
                        attachments.append(screenshot_path)
                    raise BrowserSessionError(attachments=attachments) from e

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
        if self.debug_level >= 1:
            print("Overriding user agent:", fixed)  # noqa: T201
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
    SIGNED_OUT_GREETING = re.compile(r"^\s*sign in\s*$", re.IGNORECASE)

    def __post_init__(self) -> None:
        super().__post_init__()

    def __enter__(self) -> Self:
        super().__enter__()
        self.load_site_home()
        return self

    def load_site_home(self) -> None:
        self.page.goto("https://www.safeway.com")
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
        if self.debug_level >= 1:
            print("Wrote state file:", state_file)  # noqa: T201

    def login(self) -> None:
        if self.is_signed_in():
            print("Already signed in")  # noqa: T201
            return
        self.sign_in()
        if not self.is_signed_in(wait=True):
            raise RuntimeError("Sign in did not complete")
        print("Signed in")  # noqa: T201

    @cached_property
    def page(self) -> Page:
        page = super().page

        def log_navigation(frame: Frame) -> None:
            if self.debug_level >= 1 and frame == self.page.main_frame:
                print("Navigated:", frame.url)  # noqa: T201

        page.on("framenavigated", log_navigation)

        def dismiss_cookie_banner(banner: Locator) -> None:
            print("Dismissing cookie banner")  # noqa: T201
            # The site reloads the page after cookie consent is chosen
            with (
                suppress(PlaywrightTimeoutError),
                self.page.expect_navigation(timeout=5000),
            ):
                banner.get_by_role(
                    "button", name=re.compile("necessary only", re.IGNORECASE)
                ).click()

        page.add_locator_handler(
            page.get_by_role("region", name="Cookie banner"),
            dismiss_cookie_banner,
        )

        def dismiss_info_modal(modal: Locator) -> None:
            print("Dismissing personal info confirmation modal")  # noqa: T201
            # The site reloads the page after the modal is closed
            with (
                suppress(PlaywrightTimeoutError),
                self.page.expect_navigation(timeout=5000),
            ):
                modal.get_by_role(
                    "button", name=re.compile(r"^close$", re.IGNORECASE)
                ).click()

        page.add_locator_handler(
            page.get_by_role("dialog", name="Verify 180 Days Modal"),
            dismiss_info_modal,
        )

        return page

    @property
    def _account_button(self) -> Locator:
        return self.page.get_by_role(
            "button", name=re.compile(r"^account menu$", re.IGNORECASE)
        )

    def is_signed_in(self, *, wait: bool = False) -> bool:
        greeting = self._account_button.locator(".user-greeting")
        greeting.wait_for()
        self.page.wait_for_load_state("load")
        signed_in = greeting.filter(has_not_text=self.SIGNED_OUT_GREETING)
        if wait:
            with suppress(PlaywrightTimeoutError):
                signed_in.wait_for(timeout=self.DEFAULT_TIMEOUT)
        with suppress(PlaywrightTimeoutError):
            if signed_in.count():
                return bool(signed_in.inner_text(timeout=1000).strip())
        return False

    def open_sign_in_modal(self) -> Locator | None:
        if not (panel := self.open_sign_in_panel()):
            return None
        panel.get_by_role(
            "button", name=re.compile(r"^sign in$", re.IGNORECASE)
        ).click()
        modal = self.page.get_by_role("dialog", name="Sign in modal")
        modal.wait_for()
        print("Sign in modal open")  # noqa: T201
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
                open_menu.first.wait_for(timeout=10000)
            except PlaywrightTimeoutError:
                if time.monotonic() >= deadline:
                    break
                print(  # noqa: T201
                    "Sign in panel didn't open, reloading page"
                    f" (attempt {attempt + 1})"
                )
                self.load_site_home()
                continue
            if signed_in_menu.is_visible():
                if self.debug_level >= 1:
                    print("Account menu shows a signed in user")  # noqa: T201
                return None
            if self.debug_level >= 1:
                print(f"Sign in panel open after attempt {attempt}")  # noqa: T201
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

    def sign_in(self) -> None:
        self.restore_saved_device_id()
        if not (modal := self.open_sign_in_modal()):
            return

        def _log_auth_response(response: Response) -> None:
            if response.request.resource_type not in {"xhr", "fetch"}:
                return
            url = urllib.parse.urlsplit(response.url)
            if not re.search(r"safeway\.com|albertsons|okta|ciam", url.netloc):
                return
            if self.debug_level >= 1:
                print(  # noqa: T201
                    f"Response: {response.status} {response.request.method}"
                    f" {url.netloc}{url.path}"
                )

        def continue_with_password(email: str) -> None:
            modal.get_by_role("textbox", name="Email or mobile number").fill(
                email
            )
            modal.get_by_role("button", name="Sign in with password").click()
            print("Clicked Sign in with password")  # noqa: T201
            self.page.wait_for_timeout(5000)

        if self.account.username:
            self.page.on("response", _log_auth_response)
            continue_with_password(self.account.username)
            if self.account.password:
                self.submit_password(modal, self.account.password)

    def submit_password(self, modal: Locator, password: str) -> None:
        modal.get_by_role("textbox", name="Password").fill(password)
        with self.page.expect_response(
            lambda r: urllib.parse.urlsplit(r.url).path.endswith(
                "/csms/authn/factors/password/verify"
            )
        ) as verify:
            modal.get_by_role(
                "button", name=re.compile(r"^sign in$", re.IGNORECASE)
            ).click()
        print("Clicked Sign in")  # noqa: T201
        if (destination := self.verification_required(verify.value)) is None:
            return
        print(f"Safeway requires device verification ({destination})")  # noqa: T201
        if not self.headless:
            input(
                "Complete device verification in the browser window,"
                " then press Enter here to continue: "
            )
            if not self.is_signed_in(wait=True):
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
            print(f"Verifying with: {option.inner_text().strip()}")  # noqa: T201
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
                print("The verification code is 6 digits")  # noqa: T201
                continue
            tries += 1
            code_box.fill(code)
            with self.page.expect_response(_factor_action("verify")) as verify:
                modal.get_by_role(
                    "button", name=re.compile(r"^sign in$", re.IGNORECASE)
                ).click()
            if verify.value.ok:
                print("Device verified")  # noqa: T201
                return
            print(  # noqa: T201
                "Verification code not accepted"
                f" ({self.error_message(verify.value)})"
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
    debug_level: int = field(default=0, kw_only=True)
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
            account=self.account,
            headless=self.headless,
            debug_level=self.debug_level,
        ) as browser:
            self.user_agent = browser.user_agent
            if self.debug_level >= 1:
                print(f"User Agent: {self.user_agent}")  # noqa: T201

            if not self.dry_run:
                browser.login()
            elif browser.is_signed_in():
                print("Already signed in")  # noqa: T201
            else:
                raise NotSignedIn(self.account)

            print("Retrieve session information")  # noqa: T201
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
            if self.debug_level >= 1:
                print(f"Device ID: {device_id}")  # noqa: T201
            if device_id and not browser.state.get("device_id"):
                browser.state |= {"device_id": device_id}
            if not (store_id := session_info["info"]["J4U"]["storeId"]):
                raise ValueError("Unable to retrieve store ID")
            self.store_id = store_id

            if not self.headless:
                browser.page.wait_for_timeout(1000)
                input(
                    "Complete any interaction in the browser window,"
                    " then press Enter here to continue: "
                )
