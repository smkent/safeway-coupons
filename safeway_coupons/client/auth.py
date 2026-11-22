from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from safeway_coupons.console import log
from safeway_coupons.errors import AuthenticationFailure, BrowserSessionError

from .browser import SafewayBrowserSession

if TYPE_CHECKING:
    from safeway_coupons.account import Account


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
