import json
import time
import urllib
from typing import Any, Optional

import requests
import selenium.webdriver.support.expected_conditions as ec
import undetected_chromedriver as uc  # type: ignore
from selenium.webdriver.remote.webdriver import By
from selenium.webdriver.support.wait import WebDriverWait

from .accounts import Account
from .errors import AuthenticationFailure


class BaseSession:
    USER_AGENT = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:103.0) "
        "Gecko/20100101 Firefox/103.0"
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
    def __init__(self, account: Account) -> None:
        self.access_token: Optional[str] = None
        self.store_id: Optional[str] = None
        try:
            self._login(account)
        except Exception as e:
            raise AuthenticationFailure(e, account) from e

    def _login(self, account: Account) -> None:
        screenshot_dir = "/data"
        options = uc.ChromeOptions()
        for option in [
            "--incognito",
            "--no-sandbox",
            "--disable-extensions",
            "--disable-application-cache",
            "--disable-gpu",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--headless=new",
        ]:
            options.add_argument(option)
        with uc.Chrome(options=options) as driver:
            driver.implicitly_wait(10)
            # Navigate to the website URL
            url = "https://www.safeway.com"
            print("GO", url)
            driver.get(url)
            print("CLICK")
            button = driver.find_element(
                By.XPATH, "//button [contains(text(), 'Necessary Only')]"
            )
            if button:
                print("click no cookie-button")
                button.click()
            print("SS 0")
            driver.save_screenshot(f"{screenshot_dir}/screenshot_0.png")
            driver.find_element(
                By.XPATH, "//span [contains(text(), 'Sign In')]"
            ).click()
            time.sleep(2)
            driver.find_element(
                By.XPATH, "//a [contains(text(), 'Sign In')]"
            ).click()
            time.sleep(2)

            driver.find_element(By.ID, "label-email").send_keys(
                account.username
            )
            driver.find_element(By.ID, "label-password").send_keys(
                account.password
            )
            print("CLICK 2")
            time.sleep(0.5)
            driver.find_element(
                By.XPATH, "//span [contains(text(), 'Keep Me Signed In')]"
            ).click()
            print("SS 1")
            driver.save_screenshot(f"{screenshot_dir}/screenshot_1.png")
            # print("RETURN")
            # return
            time.sleep(0.5)
            print("CLICK 3")
            driver.find_element("id", "btnSignIn").click()
            time.sleep(0.5)
            wdw = WebDriverWait(driver, 10)
            wdw.until(
                ec.text_to_be_present_in_element(
                    (By.XPATH, '//span [contains(@class, "user-greeting")]'),
                    "Account",
                )
            )
            el = driver.find_element(
                By.XPATH, '//span [contains(@class, "user-greeting")]'
            )
            print("TEXT", el.text)
            print("SS 2")
            driver.save_screenshot(f"{screenshot_dir}/screenshot_2.png")
            print("PRINT COOKIE")
            session_cookie = self._parse_cookie_value(
                driver.get_cookie("SWY_SHARED_SESSION")["value"]
            )
            session_info_cookie = self._parse_cookie_value(
                driver.get_cookie("SWY_SHARED_SESSION_INFO")["value"]
            )
            from pprint import pprint

            print("SESSION COOKIE")
            pprint(session_cookie)
            print("SESSION INFO COOKIE")
            pprint(session_info_cookie)
            print("SESSION COOKIE ACCESS TOKEN")
            pprint(session_cookie["accessToken"])
            self.access_token = session_cookie["accessToken"]
            print("SESSION COOKIE STORE ID")
            try:
                pprint(session_info_cookie["info"]["J4U"]["storeId"])
                self.store_id = session_info_cookie["info"]["J4U"]["storeId"]
            except Exception as e:
                raise Exception("Unable to retrieve store ID") from e
            print("DONE LOGGING IN")

    def _parse_cookie_value(self, value: str) -> Any:
        return json.loads(urllib.parse.unquote(value))
