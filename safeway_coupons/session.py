from __future__ import annotations

import json
import re
import tempfile
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

from .errors import AuthenticationFailure

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from patchright.sync_api import (
        Cookie,
        Frame,
        Locator,
        Page,
        Playwright,
        Response,
    )

    from .accounts import Account


class ExceptionWithAttachmentsError(Exception):
    def __init__(
        self, *args: object, attachments: list[Path] | None = None
    ) -> None:
        super().__init__(*args)
        self.attachments = attachments


@dataclass
class BrowserSession(ExitStack, ABC):
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
    def data_dir(self) -> Path: ...

    @cached_property
    def profile_dir(self) -> Path:
        return self.data_dir / "profile"

    @cached_property
    def debug_dir(self) -> Path:
        return self.data_dir / "debug"

    @cached_property
    def configured_profile_dir(self) -> Path:
        dd = self.profile_dir
        dd.mkdir(parents=True, exist_ok=True)
        prefs_path = dd / "Default" / "Preferences"
        prefs_path.parent.mkdir(parents=True, exist_ok=True)
        prefs = (
            json.loads(prefs_path.read_text()) if prefs_path.is_file() else {}
        )
        # Show new tab page on startup
        prefs.setdefault("session", {})["restore_on_startup"] = 5
        # Don't offer to restore crashed sessions
        prefs.setdefault("profile", {})["exit_type"] = "Normal"
        prefs_path.write_text(json.dumps(prefs))
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
                    if self.debug_dir:
                        self.debug_dir.mkdir(parents=True, exist_ok=True)
                        screenshot_path = self.debug_dir / "screenshot.png"
                        with suppress(Exception):
                            page.screenshot(path=screenshot_path)
                            print(f"Screenshot saved: {screenshot_path}")  # noqa: T201
                        if screenshot_path.is_file():
                            attachments.append(screenshot_path)
                    raise ExceptionWithAttachmentsError(
                        e, attachments=attachments
                    ) from e

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
        self.page.goto("https://www.safeway.com")
        return self

    @cached_property
    def data_dir(self) -> Path:
        return self.account.state_dir / f"browser-{self.channel.lower()}"

    @cached_property
    def state_file(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def state(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            return self.STATE_FILE_BASE.copy()
        return json.loads(self.state_file.read_text())

    @state.setter
    def state(self, value: dict[str, Any]) -> None:
        new_value = self.STATE_FILE_BASE | value
        with tempfile.TemporaryDirectory(dir=self.state_file.parent) as td:
            tf = Path(td) / self.state_file.name
            with tf.open("w") as file:
                json.dump(new_value, fp=file, indent=4)
            tf.replace(self.state_file)
        if self.debug_level >= 1:
            print("Wrote state file:", self.state_file)  # noqa: T201

    def login(self) -> None:
        if not self.is_signed_in():
            self.sign_in()
            if not self.is_signed_in(wait=15000):
                raise Exception("Sign in did not complete")  # noqa: TRY002
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
                modal.get_by_role("button", name="Close", exact=True).click()

        page.add_locator_handler(
            page.get_by_role("dialog", name="Verify 180 Days Modal"),
            dismiss_info_modal,
        )

        return page

    @property
    def _account_button(self) -> Locator:
        return self.page.get_by_role("button", name="Account menu", exact=True)

    def is_signed_in(self, *, wait: int | None = None) -> bool:
        greeting = self._account_button.locator(".user-greeting")
        greeting.wait_for()
        self.page.wait_for_load_state("load")
        signed_in = greeting.filter(has_not_text=self.SIGNED_OUT_GREETING)
        if wait is not None:
            with suppress(PlaywrightTimeoutError):
                signed_in.wait_for(timeout=wait)
        with suppress(PlaywrightTimeoutError):
            if signed_in.count():
                return bool(signed_in.inner_text(timeout=1000).strip())
        return False

    def open_sign_in_modal(self) -> Locator | None:
        if not (panel := self.open_sign_in_panel()):
            return None
        panel.get_by_role("button", name="Sign in", exact=True).click()
        modal = self.page.get_by_role("dialog", name="Sign in modal")
        modal.wait_for()
        print("Sign in modal open")  # noqa: T201
        return modal

    def open_sign_in_panel(self, attempts: int = 3) -> Locator | None:
        panel = self.page.get_by_role(
            "dialog", name=re.compile("account menu", re.IGNORECASE)
        )
        signed_in_menu = self.page.locator(".myaccount-flyout-wrapper")
        # Both menus are in the page, but only the open one is visible
        open_menu = panel.or_(signed_in_menu).filter(visible=True)
        for attempt in range(1, attempts + 1):
            # Clicking again while a menu is open would be blocked by it
            if not open_menu.count():
                self._account_button.click()
            try:
                open_menu.first.wait_for(timeout=5000)
            except PlaywrightTimeoutError:
                if self.debug_level >= 1:
                    print(f"Sign in panel not open after attempt {attempt}")  # noqa: T201
                continue
            if signed_in_menu.is_visible():
                if self.debug_level >= 1:
                    print("Account menu shows a signed in user")  # noqa: T201
                return None
            if self.debug_level >= 1:
                print(f"Sign in panel open after attempt {attempt}")  # noqa: T201
            return panel
        msg = f"Sign in panel did not open after {attempts} attempts"
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
            modal.get_by_role("button", name="Sign in", exact=True).click()
        print("Clicked Sign in")  # noqa: T201
        if (destination := self._verification_required(verify.value)) is None:
            return
        print(f"Safeway requires device verification ({destination})")  # noqa: T201
        if self.headless:
            raise Exception(  # noqa: TRY002
                f"Device verification required ({destination}),"
                " which isn't supported in headless mode"
            )
        input(
            "Complete device verification in the browser window,"
            " then press Enter here to continue: "
        )
        if not self.is_signed_in(wait=15000):
            raise Exception(  # noqa: TRY002
                f"Device verification ({destination}) was not completed"
            )

    @staticmethod
    def _verification_required(response: Response) -> str | None:
        try:
            body = response.json()
        except Exception:  # noqa: BLE001
            # A successful sign in can reload the page before this is read
            return None
        if body.get("status") != "MFA_REQUIRED":
            return None
        return ", ".join(
            f.get("profile", {}).get("email") or f.get("factorType", "?")
            for f in body.get("factors", [])
        )


@dataclass
class LoginSession:
    account: Account
    access_token: str | None = field(default=None, init=False)
    store_id: str | None = field(default=None, init=False)
    user_agent: str | None = field(default=None, init=False)
    headless: bool = field(default=True, kw_only=True)
    debug_level: int = field(default=0, kw_only=True)

    def __post_init__(self) -> None:
        try:
            self._login()
        except ExceptionWithAttachmentsError as e:
            raise AuthenticationFailure(
                e, self.account, attachments=e.attachments
            ) from e
        except Exception as e:
            raise AuthenticationFailure(e, self.account) from e

    def _login(self) -> None:
        with SafewayBrowserSession(
            account=self.account,
            headless=self.headless,
            debug_level=self.debug_level,
        ) as browser:
            self.user_agent = browser.user_agent
            if self.debug_level >= 1:
                print(f"User Agent: {self.user_agent}")  # noqa: T201

            browser.login()

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
                raise Exception("Unable to retrieve store ID")  # noqa: TRY002
            self.store_id = store_id

            if not self.headless:
                browser.page.wait_for_timeout(1000)
                input(
                    "Complete any interaction in the browser window,"
                    " then press Enter here to continue: "
                )
