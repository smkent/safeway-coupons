from __future__ import annotations

import itertools
import json
import re
import sys
import tempfile
import time
import urllib
import urllib.parse
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self

from patchright.sync_api import TimeoutError as PlaywrightTimeoutError

from safeway_coupons.browser import BrowserSession
from safeway_coupons.console import log
from safeway_coupons.errors import (
    BrowserSessionError,
    MultiFactorAuthenticationRequired,
    NotSignedIn,
)
from safeway_coupons.models.safeway.auth import AuthErrorResponse, AuthResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

    from patchright.sync_api import Cookie, Frame, Locator, Page, Response

    from safeway_coupons.account import Account


@dataclass
class SafewayBrowserSession(BrowserSession):
    account: Account

    STATE_FILE_BASE: ClassVar[dict[str, Any]] = {"_version": 1}
    # Non-blank greeting not starting with "Sign in", ignoring leading symbols
    SIGNED_IN_GREETING = re.compile(r"^(?!\W*sign in\b)\s*\S", re.IGNORECASE)

    def __post_init__(self) -> None:
        super().__post_init__()

    @property
    def site_url(self) -> str:
        return f"{self.account.brand.origin}/"

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

    @property
    def cookies(self) -> Mapping[str, Cookie]:
        return {c["name"]: c for c in self.page.context.cookies(self.site_url)}

    def load_site_home(self) -> None:
        self.page.goto(self.site_url)
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
            if not (
                url.netloc == self.account.brand.host
                or re.search(r"albertsons|okta|ciam", url.netloc)
            ):
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
            if not (
                (password_field := self.account.password)
                and (password := password_field.get_secret_value())
            ):
                raise BrowserSessionError(
                    message=(
                        f"Account {self.account.name} needs to sign in,"
                        " but has no password configured"
                    )
                )
            password_button = modal.get_by_role(
                "button", name="Sign in with password"
            )
            password_button.wait_for()
            self.enter_username(modal)
            password_button.click()
            log.info("Clicked Sign in with password")
            self.submit_password(modal, password)
        if not self.is_signed_in():
            raise RuntimeError("Sign in did not complete")
        log.info("Signed in")

    def enter_username(self, modal: Locator) -> None:
        username_input = modal.get_by_role(
            "textbox", name="Email or mobile number"
        )
        if username_input.is_enabled():
            username_input.fill(self.account.username)
            return
        prefilled_username = username_input.input_value().strip()
        if prefilled_username.lower() == self.account.username.strip().lower():
            log.info("Sign in form already has this account's sign in name")
            return
        log.error(
            "Sign in form is prefilled with an unexpected sign in name"
            " (%s). To sign in as %s, delete this account's browser profile"
            " directory and run again: %s",
            prefilled_username,
            self.account.username,
            self.configured_profile_dir,
        )
        raise BrowserSessionError(
            message=(
                "Sign in form is prefilled with an unexpected sign in name"
                f" ({prefilled_username})"
            )
        )

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
        log.info(
            "%s requires device verification (%s)",
            self.account.brand.display_name,
            destination,
        )
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
