import random

from .session import BaseSession, LoginSession


class SafewayAPIClient(BaseSession):
    def __init__(self, username: str, password: str) -> None:
        self.session = LoginSession(username, password)
        self.rs.headers.update(
            {
                "Authorization": f"Bearer {self.session.access_token}",
                "X-SWY_API_KEY": "emjou",
                "X-SWY_VERSION": "1.1",
                "X-SWY-APPLICATION-TYPE": "web",
            }
        )

    def get_coupons(self) -> None:
        print("get coupons")
        response = self.rs.get(
            "https://www.safeway.com/abs/pub/xapi"
            "/offers/companiongalleryoffer"
            f"?storeId={self.session.store_id}"
            f"&rand={random.randrange(100000,999999)}",
        )
        print(response)
        print(response.text)
