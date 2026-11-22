from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from safeway_coupons.client.browser import SafewayBrowserSession

MFA_REQUIRED = {
    "status": "MFA_REQUIRED",
    "factorResult": "SUCCESS",
    "factors": [
        {
            "id": "factor_id",
            "factorType": "email",
            "profile": {"email": "n***@o***.example"},
        }
    ],
}


def json_response(body: Any) -> MagicMock:
    response = MagicMock()
    response.json.return_value = body
    return response


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (MFA_REQUIRED, "n***@o***.example"),
        (
            {"status": "MFA_REQUIRED", "factors": [{"factorType": "sms"}]},
            "sms",
        ),
        ({"status": "MFA_REQUIRED", "factors": [{}]}, "?"),
        ({"status": "SUCCESS"}, None),
        (["unexpected"], None),
    ],
)
def test_verification_required(
    body: dict[str, Any], expected: str | None
) -> None:
    assert (
        SafewayBrowserSession.verification_required(json_response(body))
        == expected
    )


def test_verification_required_unreadable_response() -> None:
    response = MagicMock()
    response.json.side_effect = ValueError("page reloaded")
    assert SafewayBrowserSession.verification_required(response) is None


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            {"errors": [{"errorCode": "CSMS0120", "message": "Invalid code"}]},
            "Invalid code",
        ),
        (None, "HTTP 400"),
    ],
)
def test_error_message(body: Any, expected: str) -> None:
    response = json_response(body)
    response.status = 400
    assert SafewayBrowserSession.error_message(response) == expected
