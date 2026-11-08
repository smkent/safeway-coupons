import json
import time
import urllib.parse
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import responses

from safeway_coupons.session import DEFAULT_TOKEN_ENDPOINT, LoginSession

from .utils import create_account

SESSION_INFO = {"info": {"J4U": {"storeId": "1983"}}}


def encode_cookie(value: dict[str, Any]) -> str:
    return urllib.parse.quote(json.dumps(value))


def make_session_cookie(**overrides: Any) -> dict[str, Any]:
    now = time.time()
    cookie = {
        "accessToken": "old_access_token",
        "refreshToken": "old_refresh_token",
        "issueTime": int((now - 3000) * 1000),
        "expireTime": int(now * 1000),
    }
    cookie.update(overrides)
    return cookie


def write_session_file(path: Path, cookie: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "accounts": {
                    create_account().username: {
                        "session": cookie,
                        "session_info": SESSION_INFO,
                    }
                },
            }
        )
    )


@pytest.fixture(autouse=True)
def clear_session_env(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    for name in (
        "SWY_SESSION_FILE",
        "SWY_SHARED_SESSION",
        "SWY_SHARED_SESSION_INFO",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


def test_refresh_expired_env_cookie(
    http_responses: responses.RequestsMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWY_SHARED_SESSION", encode_cookie(make_session_cookie()))
    monkeypatch.setenv(
        "SWY_SHARED_SESSION_INFO", encode_cookie(SESSION_INFO)
    )
    http_responses.add(
        responses.POST,
        DEFAULT_TOKEN_ENDPOINT,
        json={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        },
    )

    session = LoginSession(create_account(), None)

    assert session.access_token == "new_access_token"
    assert session.store_id == "1983"
    assert session.session_cookie
    assert session.session_cookie["refreshToken"] == "new_refresh_token"
    assert session.session_cookie["expireTime"] > time.time() * 1000
    assert len(http_responses.calls) == 1
    body = http_responses.calls[0].request.body
    assert isinstance(body, str)
    assert "grant_type=refresh_token" in body
    assert "refresh_token=old_refresh_token" in body


def test_valid_env_cookie_is_not_refreshed(
    http_responses: responses.RequestsMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cookie = make_session_cookie(
        expireTime=int((time.time() + 3600) * 1000)
    )
    monkeypatch.setenv("SWY_SHARED_SESSION", encode_cookie(cookie))
    monkeypatch.setenv(
        "SWY_SHARED_SESSION_INFO", encode_cookie(SESSION_INFO)
    )

    session = LoginSession(create_account(), None)

    assert session.access_token == "old_access_token"
    assert not http_responses.calls


@pytest.mark.usefixtures("login_success")
def test_refresh_failure_falls_back_to_browser(
    http_responses: responses.RequestsMock,
    monkeypatch: pytest.MonkeyPatch,
    mock_undetected_chromedriver: Any,
) -> None:
    monkeypatch.setenv("SWY_SHARED_SESSION", encode_cookie(make_session_cookie()))
    monkeypatch.setenv(
        "SWY_SHARED_SESSION_INFO", encode_cookie(SESSION_INFO)
    )
    http_responses.add(
        responses.POST,
        DEFAULT_TOKEN_ENDPOINT,
        status=400,
        json={"error": "invalid_grant"},
    )

    session = LoginSession(create_account(), None)

    assert session.access_token == "test_token"
    assert mock_undetected_chromedriver.get.called


@pytest.mark.usefixtures("login_success")
def test_expired_cookie_without_refresh_token_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    mock_undetected_chromedriver: Any,
) -> None:
    cookie = make_session_cookie()
    del cookie["refreshToken"]
    monkeypatch.setenv("SWY_SHARED_SESSION", encode_cookie(cookie))
    monkeypatch.setenv(
        "SWY_SHARED_SESSION_INFO", encode_cookie(SESSION_INFO)
    )

    session = LoginSession(create_account(), None)

    assert session.access_token == "test_token"
    assert mock_undetected_chromedriver.get.called


def test_browser_login_persists_session_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    login_success: None,
) -> None:
    path = tmp_path / "session.json"
    monkeypatch.setenv("SWY_SESSION_FILE", str(path))

    session = LoginSession(create_account(), None)

    assert session.access_token == "test_token"
    data = json.loads(path.read_text())
    entry = data["accounts"][create_account().username]
    assert entry["session"]["accessToken"] == "test_token"
    assert entry["session_info"]["info"]["J4U"]["storeId"] == 42
    assert path.stat().st_mode & 0o777 == 0o600


def test_session_file_is_used_before_browser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_undetected_chromedriver: Any,
) -> None:
    path = tmp_path / "session.json"
    cookie = make_session_cookie(
        accessToken="file_access_token",
        refreshToken="file_refresh_token",
        expireTime=int((time.time() + 3600) * 1000),
    )
    write_session_file(path, cookie)
    monkeypatch.setenv("SWY_SESSION_FILE", str(path))

    session = LoginSession(create_account(), None)

    assert session.access_token == "file_access_token"
    assert not mock_undetected_chromedriver.get.called


def test_refresh_updates_session_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_responses: responses.RequestsMock,
) -> None:
    path = tmp_path / "session.json"
    write_session_file(path, make_session_cookie())
    monkeypatch.setenv("SWY_SESSION_FILE", str(path))
    http_responses.add(
        responses.POST,
        DEFAULT_TOKEN_ENDPOINT,
        json={
            "access_token": "new_access_token",
            "refresh_token": "rotated_refresh_token",
            "expires_in": 3600,
        },
    )

    session = LoginSession(create_account(), None)

    assert session.access_token == "new_access_token"
    data = json.loads(path.read_text())
    entry = data["accounts"][create_account().username]
    assert entry["session"]["accessToken"] == "new_access_token"
    assert entry["session"]["refreshToken"] == "rotated_refresh_token"
    assert entry["session"]["expireTime"] > time.time() * 1000
