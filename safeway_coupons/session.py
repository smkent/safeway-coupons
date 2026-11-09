from __future__ import annotations

import json
import time
import urllib
import urllib.parse
from contextlib import contextmanager, suppress
from typing import TYPE_CHECKING, Any

import requests
import requests.adapters
import selenium.webdriver.support.expected_conditions as ec
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import By
from selenium.webdriver.support.wait import WebDriverWait

from .chrome_driver import chrome_driver
from .errors import AuthenticationFailure

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    import undetected_chromedriver as uc

    from .accounts import Account


class ExceptionWithAttachmentsError(Exception):
    def __init__(
        self, *args: object, attachments: list[Path] | None = None
    ) -> None:
        super().__init__(*args)
        self.attachments = attachments


class BaseSession:
    USER_AGENT = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) "
        "Gecko/20100101 Firefox/122.0"
    )

    @property
    def session_requests(self) -> requests.Session:
        if not hasattr(self, "_requests"):
            session = requests.Session()
            session.mount(
                "https://", requests.adapters.HTTPAdapter(pool_maxsize=1)
            )
            session.headers.update({"DNT": "1", "User-Agent": self.USER_AGENT})
            self._requests = session
        return self._requests


class LoginSession(BaseSession):
    def __init__(self, account: Account, debug_dir: Path | None) -> None:
        self.access_token: str | None = None
        self.store_id: str | None = None
        self.debug_dir: Path | None = debug_dir
        try:
            self._login(account)
        except ExceptionWithAttachmentsError as e:
            raise AuthenticationFailure(
                e, account, attachments=e.attachments
            ) from e
        except Exception as e:
            raise AuthenticationFailure(e, account) from e

    @contextmanager
    def _chrome_driver(self, *, headless: bool = True) -> Generator[uc.Chrome]:
        try:
            with chrome_driver(headless=headless) as driver:
                yield driver
        except WebDriverException as e:
            attachments: list[Path] = []
            if self.debug_dir:
                path = self.debug_dir / "screenshot.png"
                with suppress(WebDriverException):
                    driver.save_screenshot(path)
                    attachments.append(path)
            raise ExceptionWithAttachmentsError(
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

    def _login(self, account: Account) -> None:
        with self._chrome_driver() as driver:
            driver.implicitly_wait(10)
            wait = WebDriverWait(driver, 10)
            # Navigate to the website URL
            url = "https://www.safeway.com"
            print("Connect to safeway.com")  # noqa: T201
            driver.get(url)  # ty: ignore[invalid-argument-type, missing-argument]
            try:
                button = driver.find_element(
                    By.XPATH,
                    "//button [contains(text(), 'Necessary Only')]",
                )
                if button:
                    print("Decline cookie prompt")  # noqa: T201
                    button.click()
                    print(  # noqa: T201
                        "Return to safeway.com after declining cookie prompt"
                    )
                    driver.get(url)  # ty: ignore[invalid-argument-type, missing-argument]
            except NoSuchElementException:
                print("Skipping cookie prompt which is not present")  # noqa: T201
            print("Open Sign In sidebar")  # noqa: T201
            wait.until(
                ec.visibility_of_element_located(
                    (By.XPATH, "//span [contains(text(), 'Sign In')]")
                )
            ).click()
            print("Open Sign In form")  # noqa: T201
            wait.until(
                ec.visibility_of_element_located(
                    (By.XPATH, "//button [contains(text(), 'Sign in')]")
                )
            ).click()
            time.sleep(2)
            print("Populate Sign In form username")  # noqa: T201
            driver.find_element(By.ID, "enterUsername").send_keys(
                account.username
            )
            time.sleep(0.5)
            print("Click Sign in with password button")  # noqa: T201
            driver.find_element(
                By.XPATH, '//button[contains(text(), "Sign in with password")]'
            ).click()
            time.sleep(2)
            driver.find_element(By.ID, "password").send_keys(account.password)
            time.sleep(0.5)
            print("Click Sign In button")  # noqa: T201
            driver.find_element(
                By.XPATH, '//button[contains(text(), "Sign In")]'
            ).click()
            time.sleep(0.5)
            print("Wait for signed in landing page to load")  # noqa: T201
            wait.until(self._sign_in_success)
            print("Retrieve session information")  # noqa: T201
            session_cookie = self._parse_cookie(
                driver.get_cookie("SWY_SHARED_SESSION")
            )
            session_info_cookie = self._parse_cookie(
                driver.get_cookie("SWY_SHARED_SESSION_INFO")
            )
            self.access_token = session_cookie["accessToken"]
            try:
                self.store_id = session_info_cookie["info"]["J4U"]["storeId"]
            except Exception as e:
                raise Exception("Unable to retrieve store ID") from e  # noqa: TRY002

    def _parse_cookie(self, value: dict[Any, Any] | None) -> Any:
        if value is None:
            raise ValueError("No cookie value retrieved")
        return json.loads(urllib.parse.unquote(value["value"]))
