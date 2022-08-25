import json
import os

import responses
from pytest_mock import MockerFixture

from safeway_coupons import Account, SafewayCoupons


def test_safeway_coupons(
    mocker: MockerFixture, http_responses: responses.RequestsMock
) -> None:
    mocker.patch.object(
        os,
        "environ",
        {
            "SAFEWAY_COUPONS_USERNAME": "ness@onett.example",
            "SAFEWAY_COUPONS_PASSWORD": "pk_fire",
        },
    )
    http_responses.add(
        method=responses.POST,
        url="https://albertsons.okta.com/api/v1/authn",
        body=json.dumps({"status": "SUCCESS", "sessionToken": "test"}),
    )

    session_data = {"accessToken": "test_token"}
    session_info = {"info": {"J4U": {"storeId": 42}}}
    http_responses.add(
        method=responses.GET,
        url=(
            "https://albertsons.okta.com"
            "/oauth2/ausp6soxrIyPrm8rS2p6/v1/authorize"
        ),
        headers={
            "Set-Cookie": f"SWY_SHARED_SESSION={json.dumps(session_data)} ",
            "set-cookie": (
                f"SWY_SHARED_SESSION_INFO={json.dumps(session_info)}"
            ),
        },
    )
    http_responses.add(
        method=responses.GET,
        url=(
            "https://www.safeway.com/abs/pub/xapi/offers/companiongalleryoffer"
        ),
        body=json.dumps({"companionGalleryOfferList": []}),
    )
    app = SafewayCoupons(
        send_email=False,
        sleep_level=2,
    )
    app.clip_for_account(
        Account(
            username="ness@onett.example",
            password="pk_fire",
            mail_from="ness@onett.example",
            mail_to="ness@onett.example",
        )
    )
