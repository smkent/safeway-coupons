import contextlib
import json
import os
import time
import urllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

import requests
import undetected_chromedriver as uc  # type: ignore
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import By
from selenium.webdriver.support.wait import WebDriverWait

from .accounts import Account
from .chrome_driver import chrome_driver
from .errors import AuthenticationFailure

# Safeway uses Albertsons' Okta authorization server for sign in. These values
# are public and are fetched from the safeway.com page configuration.
DEFAULT_TOKEN_ENDPOINT = (  # nosec B105 - public URL, not a secret
    "https://ciam.albertsons.com/oauth2/ausp6soxrIyPrm8rS2p6/v1/token"
)
DEFAULT_CLIENT_ID = "0oap6ku01XJqIRdl42p6"
DEFAULT_TOKEN_LIFETIME = 2700
# Refresh shortly before the access token expires so a long coupon run does
# not start with an almost-expired token.
REFRESH_SKEW_SECONDS = 300


class ExceptionWithAttachments(Exception):
    def __init__(
        self,
        *args: Any,
        attachments: Optional[list[Path]] = None,
        **kwargs: Any,
    ):
        self.attachments = attachments


class BaseSession:
    USER_AGENT = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) "
        "Gecko/20100101 Firefox/122.0"
    )

    @property
    def requests(self) -> requests.Session:
        if not hasattr(self, "_requests"):
            session = requests.Session()
            session.mount(
                "https://", requests.adapters.HTTPAdapter(pool_maxsize=1)
            )
            session.headers.update({"DNT": "1", "User-Agent": self.USER_AGENT})
            self._requests = session
        return self._requests


class LoginSession(BaseSession):
    def __init__(self, account: Account, debug_dir: Optional[Path]) -> None:
        self.account = account
        self.access_token: Optional[str] = None
        self.store_id: Optional[str] = None
        self.session_cookie: Optional[dict[str, Any]] = None
        self.session_info_cookie: Optional[dict[str, Any]] = None
        self.debug_dir: Optional[Path] = debug_dir
        try:
            self._login(account)
        except AuthenticationFailure:
            raise
        except ExceptionWithAttachments as e:
            raise AuthenticationFailure(
                e, account, attachments=e.attachments
            ) from e
        except Exception as e:
            raise AuthenticationFailure(e, account) from e

    @contextlib.contextmanager
    def _chrome_driver(self, headless: bool = True) -> Iterator[uc.Chrome]:
        try:
            with chrome_driver(headless=headless) as driver:
                yield driver
        except WebDriverException as e:
            attachments: list[Path] = []
            if self.debug_dir:
                path = self.debug_dir / "screenshot.png"
                with contextlib.suppress(WebDriverException):
                    driver.save_screenshot(path)
                    attachments.append(path)
            raise ExceptionWithAttachments(
                f"[{type(e).__name__}] {e}", attachments=attachments
            ) from e

    @staticmethod
    def _sign_in_result(driver: uc.Chrome) -> Optional[str]:
        """Return "success", a failure reason, or None while still pending."""
        try:
            elements = driver.find_elements(
                By.XPATH, '//span [contains(@class, "user-greeting")]'
            )
            for element in elements:
                if element.text and not element.text.lower().startswith(
                    "sign in"
                ):
                    return "success"
        except StaleElementReferenceException:
            return None
        try:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
        except (NoSuchElementException, StaleElementReferenceException):
            return None
        if "password entered doesn't match" in body or (
            "password" in body
            and ("incorrect" in body or "doesn't match" in body)
        ):
            return "bad-password"
        if "send code to" in body or "new device" in body:
            return "verify-device"
        return None

    @staticmethod
    def _try_click(driver: uc.Chrome, locator: tuple[str, str]) -> bool:
        try:
            for element in driver.find_elements(*locator):
                if element.is_displayed() and element.is_enabled():
                    element.click()
                    return True
        except (
            StaleElementReferenceException,
            ElementClickInterceptedException,
            ElementNotInteractableException,
        ):
            return False
        return False

    @classmethod
    def _open_sign_in_form(
        cls, wait: WebDriverWait, timeout: float = 30
    ) -> None:
        """Open the account menu and click its "Sign in" item.

        The account link is present before the page's JavaScript is ready,
        so an early click can be silently ignored. Keep trying until the
        menu item is actually displayed and clickable.
        """
        menu_item = (
            By.XPATH,
            "//*[@id='signin-dropdown']"
            "//button[normalize-space()='Sign in']",
        )
        state = {"last_toggle": 0.0}

        def attempt(driver: uc.Chrome) -> bool:
            if cls._try_click(driver, menu_item):
                return True
            # Re-click the account control periodically in case the page
            # was not yet interactive when it was first clicked.
            now = time.time()
            if now - state["last_toggle"] >= 4:
                state["last_toggle"] = now
                cls._try_click(driver, (By.ID, "auth_signin_link"))
            return False

        wait.until(attempt)

    @staticmethod
    def _click(wait: WebDriverWait, locator: tuple[str, str]) -> None:
        """Click an element, retrying if the page re-renders under us."""

        def attempt(driver: uc.Chrome) -> bool:
            try:
                element = driver.find_element(*locator)
                if not (element.is_displayed() and element.is_enabled()):
                    return False
                element.click()
                return True
            except (
                NoSuchElementException,
                StaleElementReferenceException,
                ElementClickInterceptedException,
                ElementNotInteractableException,
            ):
                return False

        wait.until(attempt)

    @staticmethod
    def _send_keys(
        wait: WebDriverWait, locator: tuple[str, str], text: str
    ) -> None:
        """Type into an element, retrying if the page re-renders under us."""

        def attempt(driver: uc.Chrome) -> bool:
            try:
                element = driver.find_element(*locator)
                if not element.is_displayed():
                    return False
                element.clear()
                element.send_keys(text)
                return True
            except (
                NoSuchElementException,
                StaleElementReferenceException,
                ElementNotInteractableException,
            ):
                return False

        wait.until(attempt)

    @staticmethod
    def _session_file_path() -> Optional[Path]:
        value = os.environ.get("SWY_SESSION_FILE")
        return Path(value).expanduser() if value else None

    def _read_session_file(self) -> dict[str, Any]:
        """Return the stored sessions keyed by account username."""
        path = self._session_file_path()
        if path is None or not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as e:
            print(
                f"Warning: cannot read Safeway session file {path} ({e}); "
                "ignoring it"
            )
            return {}
        if not isinstance(data, dict):
            print(
                f"Warning: unexpected Safeway session file format in {path}; "
                "ignoring it"
            )
            return {}
        accounts = data.get("accounts")
        if isinstance(accounts, dict):
            return accounts
        # Accept a simple single-account format as well, for compatibility
        # with hand-written session files.
        username = data.get("username")
        session = data.get("session")
        if isinstance(username, str) and isinstance(session, dict):
            return {
                username: {
                    "session": session,
                    "session_info": data.get("session_info"),
                }
            }
        return {}

    def _persist_session(self) -> None:
        """Save the current session so rotated refresh tokens survive."""
        path = self._session_file_path()
        if (
            path is None
            or self.session_cookie is None
            or self.session_info_cookie is None
        ):
            return
        try:
            accounts = self._read_session_file()
            accounts[self.account.username] = {
                "session": self.session_cookie,
                "session_info": self.session_info_cookie,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            fd = os.open(
                temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
            )
            with os.fdopen(fd, "w") as f:
                json.dump({"version": 1, "accounts": accounts}, f, indent=2)
                f.write("\n")
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, path)
        except OSError as e:
            print(f"Warning: cannot save Safeway session to {path} ({e})")

    def _try_session_file(self) -> bool:
        path = self._session_file_path()
        if path is None or not path.exists():
            return False
        entry = self._read_session_file().get(self.account.username)
        if not isinstance(entry, dict):
            return False
        session_cookie = entry.get("session")
        session_info_cookie = entry.get("session_info")
        if not isinstance(session_cookie, dict) or not isinstance(
            session_info_cookie, dict
        ):
            return False
        try:
            self._load_session_cookies(session_cookie, session_info_cookie)
        except Exception as e:
            print(
                f"Warning: cannot use the Safeway session in {path} ({e}); "
                "falling back"
            )
            return False
        print(f"Using Safeway session from {path}")
        self._persist_session()
        return True

    @staticmethod
    def _session_needs_refresh(session_cookie: dict[str, Any]) -> bool:
        expire_time = session_cookie.get("expireTime")
        if expire_time is None:
            return False
        try:
            expiry = int(expire_time) / 1000
        except (TypeError, ValueError):
            return False
        return expiry <= time.time() + REFRESH_SKEW_SECONDS

    def _refresh_session_cookie(
        self, session_cookie: dict[str, Any]
    ) -> dict[str, Any]:
        refresh_token = session_cookie.get("refreshToken")
        if not refresh_token:
            raise Exception(
                "session cookie is expired and has no refresh token"
            )
        response = self.requests.post(
            DEFAULT_TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": DEFAULT_CLIENT_ID,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as e:
            raise Exception(
                "token refresh returned an invalid response: "
                f"{response.text[:100]!r}"
            ) from e
        access_token = payload.get("access_token")
        if not access_token:
            raise Exception(
                "token refresh response did not include an access token"
            )
        try:
            expires_in = int(
                payload.get("expires_in") or DEFAULT_TOKEN_LIFETIME
            )
        except (TypeError, ValueError):
            expires_in = DEFAULT_TOKEN_LIFETIME
        now = time.time()
        refreshed = dict(session_cookie)
        refreshed["accessToken"] = access_token
        refreshed["refreshToken"] = (
            payload.get("refresh_token") or refresh_token
        )
        refreshed["issueTime"] = int(now * 1000)
        refreshed["expireTime"] = int((now + expires_in) * 1000)
        return refreshed

    def _load_session_cookies(
        self,
        session_cookie: dict[str, Any],
        session_info_cookie: dict[str, Any],
    ) -> None:
        if self._session_needs_refresh(session_cookie):
            print(
                "Safeway session cookie is expired or about to expire; "
                "requesting a fresh access token"
            )
            session_cookie = self._refresh_session_cookie(session_cookie)
            print("Refreshed the Safeway session access token")
        try:
            store_id = session_info_cookie["info"]["J4U"]["storeId"]
        except Exception as e:
            raise Exception("Unable to retrieve store ID") from e
        expire_time = session_cookie.get("expireTime")
        if expire_time is not None and int(expire_time) / 1000 <= time.time():
            raise Exception("session cookie has expired")
        self.access_token = session_cookie["accessToken"]
        self.store_id = store_id
        self.session_cookie = session_cookie
        self.session_info_cookie = session_info_cookie

    def _load_session_from_cookies(
        self, session_cookie_raw: str, session_info_cookie_raw: str
    ) -> None:
        self._load_session_cookies(
            self._parse_cookie_value(session_cookie_raw),
            self._parse_cookie_value(session_info_cookie_raw),
        )

    def _login(self, account: Account) -> None:
        if self._try_session_file():
            return
        env_session = os.environ.get("SWY_SHARED_SESSION")
        env_session_info = os.environ.get("SWY_SHARED_SESSION_INFO")
        if bool(env_session) != bool(env_session_info):
            print(
                "Warning: both SWY_SHARED_SESSION and "
                "SWY_SHARED_SESSION_INFO must be set to bypass browser "
                "login; ignoring the incomplete cookie configuration"
            )
        if env_session and env_session_info:
            try:
                self._load_session_from_cookies(env_session, env_session_info)
            except Exception as e:
                print(
                    "Warning: cannot use SWY_SHARED_SESSION / "
                    f"SWY_SHARED_SESSION_INFO from environment ({e}); "
                    f"lengths: SWY_SHARED_SESSION={len(env_session)}, "
                    f"SWY_SHARED_SESSION_INFO={len(env_session_info)}; "
                    "falling back to browser login"
                )
            else:
                print("Using session cookies from environment variables")
                self._persist_session()
                return
        with self._chrome_driver() as driver:
            driver.implicitly_wait(0)
            driver.set_window_size(1920, 1080)
            wait = WebDriverWait(driver, 30)
            # Navigate to the website URL
            url = "https://www.safeway.com"
            print("Connect to safeway.com")
            driver.get(url)
            try:
                button = driver.find_element(
                    By.XPATH,
                    "//button [contains(text(), 'Necessary Only')]",
                )
                if button:
                    print("Decline cookie prompt")
                    button.click()
                    print(
                        "Return to safeway.com after declining cookie prompt"
                    )
                    driver.get(url)
            except NoSuchElementException:
                print("Skipping cookie prompt which is not present")
            print("Open Sign In sidebar")
            self._open_sign_in_form(wait)
            print("Open Sign In form")
            time.sleep(2)
            print("Populate Sign In form username")
            self._send_keys(wait, (By.ID, "enterUsername"), account.username)
            time.sleep(0.5)
            print("Click Sign in with password button")
            self._click(
                wait,
                (
                    By.XPATH,
                    "//button[normalize-space()='Sign in with password']",
                ),
            )
            time.sleep(2)
            print("Populate Sign In form password")
            self._send_keys(wait, (By.ID, "password"), account.password)
            time.sleep(0.5)
            print("Click Sign In button")
            self._click(
                wait, (By.XPATH, "//button[normalize-space()='Sign In']")
            )
            time.sleep(0.5)
            print("Wait for signed in landing page to load")
            result = wait.until(self._sign_in_result)
            if result == "bad-password":
                raise AuthenticationFailure(
                    Exception(
                        "Safeway rejected the username or password "
                        "(the site reported that the password does not "
                        "match its records)"
                    ),
                    account,
                )
            if result == "verify-device":
                raise AuthenticationFailure(
                    Exception(
                        "Safeway requires verification of a new device. "
                        "Sign in once in a regular browser, complete the "
                        "verification, or use SWY_SHARED_SESSION / "
                        "SWY_SHARED_SESSION_INFO"
                    ),
                    account,
                )
            print("Signed in")
            print("Retrieve session information")
            session_cookie = driver.get_cookie("SWY_SHARED_SESSION")
            if not session_cookie:
                raise AuthenticationFailure(
                    Exception(
                        "SWY_SHARED_SESSION cookie not found after login"
                    ),
                    account,
                )
            session_cookie_raw = session_cookie["value"]

            session_info_cookie = driver.get_cookie("SWY_SHARED_SESSION_INFO")
            if not session_info_cookie:
                raise AuthenticationFailure(
                    Exception(
                        "SWY_SHARED_SESSION_INFO cookie not found after login"
                    ),
                    account,
                )
            session_info_cookie_raw = session_info_cookie["value"]

            self._load_session_from_cookies(
                session_cookie_raw, session_info_cookie_raw
            )
            self._persist_session()

    def _parse_cookie_value(self, value: str) -> Any:
        decoded = urllib.parse.unquote(value)
        try:
            return json.loads(decoded)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"invalid session cookie JSON ({e}); decoded value starts "
                f"with {decoded[:40]!r}"
            ) from e
