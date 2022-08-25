import json
import urllib
from typing import Optional

import requests

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
        # Log in
        response = self.requests.post(
            LOGIN_URL,
            json={"username": account.username, "password": account.password},
        )
        response.raise_for_status()
        login_data = response.json()
        if login_data.get("status") != "SUCCESS":
            raise Exception("Login was not successful")
        session_token = login_data["sessionToken"]
        # Retrieve session information
        state_token = make_token()
        nonce = make_nonce()
        params = {
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "response_type": "code",
            "response_mode": "query",
            "state": state_token,
            "nonce": nonce,
            "prompt": "none",
            "sessionToken": session_token,
            "scope": "openid profile email offline_access used_credentials",
        }
        url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
        response = self.requests.get(url)
        response.raise_for_status()
        session = json.loads(
            urllib.parse.unquote(self.requests.cookies["SWY_SHARED_SESSION"])
        )
        self.access_token = session["accessToken"]
        session_info = json.loads(
            urllib.parse.unquote(
                self.requests.cookies["SWY_SHARED_SESSION_INFO"]
            )
        )
        try:
            self.store_id = session_info["info"]["J4U"]["storeId"]
        except Exception as e:
            raise Exception("Unable to retrieve store ID") from e
