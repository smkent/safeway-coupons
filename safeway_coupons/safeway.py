import os

from .api_client import SafewayAPIClient


def v2() -> None:
    user = os.environ["USER"]
    password = os.environ["PASS"]
    print("done calling login")
    print("done calling get_coupons")
    api = SafewayAPIClient(user, password)
    api.get_coupons()
