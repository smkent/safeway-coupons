import contextlib
import json
import os
import time
import urllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

import requests
import selenium.webdriver.support.expected_conditions as ec
import undetected_chromedriver as uc  # type: ignore
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import By
from selenium.webdriver.support.wait import WebDriverWait

from .accounts import Account
from .chrome_driver import chrome_driver
from .errors import AuthenticationFailure


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
        self.access_token: Optional[str] = None
        self.store_id: Optional[str] = None
        self.debug_dir: Optional[Path] = debug_dir
        try:
            self._login(account)
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
    def _sign_in_success(driver: uc.Chrome) -> bool:
        try:
            element = driver.find_element(
                By.XPATH, '//span [contains(@class, "user-greeting")]'
            )
            if not (element and element.text):
                return False
            return not element.text.lower().startswith("sign in")
        except StaleElementReferenceException:
            return False

    def _load_session_from_cookies(
        self, session_cookie_raw: str, session_info_cookie_raw: str
    ) -> None:
        session_cookie = self._parse_cookie_value(session_cookie_raw)
        session_info_cookie = self._parse_cookie_value(
            session_info_cookie_raw
        )
        access_token = session_cookie["accessToken"]
        try:
            store_id = session_info_cookie["info"]["J4U"]["storeId"]
        except Exception as e:
            raise Exception("Unable to retrieve store ID") from e
        expire_time = session_cookie.get("expireTime")
        if expire_time is not None:
            if int(expire_time) / 1000 <= time.time():
                raise Exception("session cookie has expired")
        self.access_token = access_token
        self.store_id = store_id

    def _login(self, account: Account) -> None:
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
                self._load_session_from_cookies(
                    env_session, env_session_info
                )
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
                return
        with self._chrome_driver() as driver:
            driver.implicitly_wait(10)
            wait = WebDriverWait(driver, 10)
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
            wait.until(
                ec.visibility_of_element_located(
                    (By.XPATH, "//span [contains(text(), 'Sign In')]")
                )
            ).click()
            print("Open Sign In form")
            wait.until(
                ec.visibility_of_element_located(
                    (By.XPATH, "//button [contains(text(), 'Sign in')]")
                )
            ).click()
            time.sleep(2)
            print("Populate Sign In form username")
            driver.find_element(By.ID, "enterUsername").send_keys(
                account.username
            )
            time.sleep(0.5)
            print("Click Sign in with password button")
            driver.find_element(
                By.XPATH, '//button[contains(text(), "Sign in with password")]'
            ).click()
            time.sleep(2)
            driver.find_element(By.ID, "password").send_keys(account.password)
            time.sleep(0.5)
            print("Click Sign In button")
            driver.find_element(
                By.XPATH, '//button[contains(text(), "Sign In")]'
            ).click()
            time.sleep(0.5)
            print("Wait for signed in landing page to load")
            wait.until(self._sign_in_success)
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

            session_info_cookie = driver.get_cookie(
                "SWY_SHARED_SESSION_INFO"
            )
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

    def _parse_cookie_value(self, value: str) -> Any:
        decoded = urllib.parse.unquote(value)
        try:
            return json.loads(decoded)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"invalid session cookie JSON ({e}); decoded value starts "
                f"with {decoded[:40]!r}"
            ) from e
