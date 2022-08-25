import json
import os
import sys

import responses
from pytest_mock import MockerFixture

from safeway_coupons.app import main


def test_main(
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
    mocker.patch.object(sys, "argv", ["safeway-coupons"])
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
    main()
