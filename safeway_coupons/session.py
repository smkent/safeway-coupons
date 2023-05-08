import json
import time
import urllib
from typing import Optional

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from .accounts import Account
from .errors import AuthenticationFailure
from .utils import make_nonce, make_token

LOGIN_URL = "https://albertsons.okta.com/api/v1/authn"
AUTHORIZE_URL = (
    "https://albertsons.okta.com/oauth2/ausp6soxrIyPrm8rS2p6/v1/authorize"
)

OAUTH_CLIENT_ID = "0oap6ku01XJqIRdl42p6"
OAUTH_REDIRECT_URI = (
    "https://www.safeway.com/bin/safeway/unified/sso/authorize"
)

WEBDRIVER = webdriver.Firefox


class BaseSession:
    USER_AGENT = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:103.0) "
        "Gecko/20100101 Firefox/103.0"
    )

    def __del__(self) -> None:
        if getattr(self, "_browser", None):
            self._browser.close()

    @property
    def browser(self) -> WEBDRIVER:
        if not hasattr(self, "_browser"):
            self._browser = WEBDRIVER()
        return self._browser

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
        self.browser.get("https://www.safeway.com/account/sign-in.html")
        self.browser.implicitly_wait(10)
        email_input = self.browser.find_element(By.ID, "label-email")
        self.browser.implicitly_wait(10)
        password_input = self.browser.find_element(By.ID, "label-password")
        time.sleep(1)
        email_input.send_keys(account.username)
        time.sleep(1)
        password_input.send_keys(account.password + Keys.RETURN)
        self.browser.implicitly_wait(30)
        self.browser.find_element(By.ID, "skip-main-content")
        session = json.loads(
            urllib.parse.unquote(
                (self.browser.get_cookie("SWY_SHARED_SESSION") or {})["value"]
            )
        )
        self.access_token = session["accessToken"]
        session_info = json.loads(
            urllib.parse.unquote(
                (self.browser.get_cookie("SWY_SHARED_SESSION_INFO") or {})[
                    "value"
                ]
            )
        )
        try:
            self.store_id = session_info["info"]["J4U"]["storeId"]
        except Exception as e:
            raise Exception("Unable to retrieve store ID") from e
