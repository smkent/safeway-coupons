import contextlib
import json
import time
import urllib
from pathlib import Path
from typing import Any, Iterator, List, Optional

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
        attachments: Optional[List[Path]] = None,
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
            attachments: List[Path] = []
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

    def _login(self, account: Account) -> None:
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
                    (By.XPATH, "//a [contains(text(), 'Sign In')]")
                )
            ).click()
            time.sleep(2)
            print("Populate Sign In form")
            driver.find_element(By.ID, "label-email").send_keys(
                account.username
            )
            driver.find_element(By.ID, "label-password").send_keys(
                account.password
            )
            time.sleep(0.5)
            try:
                driver.find_element(
                    By.XPATH,
                    "//span [contains(text(), 'Keep Me Signed In')]",
                ).click()
                print("Deselect Keep Me Signed In")
                time.sleep(0.5)
            except NoSuchElementException:
                print(
                    "Skipping Keep Me Signed In checkbox "
                    "which is not present"
                )
            print("Click Sign In button")
            driver.find_element("id", "btnSignIn").click()
            time.sleep(0.5)
            print("Wait for signed in landing page to load")
            wait.until(self._sign_in_success)
            print("Retrieve session information")
            session_cookie = self._parse_cookie_value(
                driver.get_cookie("SWY_SHARED_SESSION")["value"]
            )
            session_info_cookie = self._parse_cookie_value(
                driver.get_cookie("SWY_SHARED_SESSION_INFO")["value"]
            )
            self.access_token = session_cookie["accessToken"]
            try:
                self.store_id = session_info_cookie["info"]["J4U"]["storeId"]
            except Exception as e:
                raise Exception("Unable to retrieve store ID") from e

    def _parse_cookie_value(self, value: str) -> Any:
        return json.loads(urllib.parse.unquote(value))
