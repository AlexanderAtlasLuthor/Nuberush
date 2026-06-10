"""Tests for the QuickBooks OAuth HTTP client (F2.27.9.B).

Drives `QuickBooksClient` with `httpx.MockTransport` — NO real network and NO
real credentials. Verifies request shape, token parsing, controlled error
handling, and that NO token / client secret / OAuth code / Authorization header
leaks into an exception message.
"""
from __future__ import annotations

import base64
import json
from datetime import UTC
from datetime import datetime
from urllib.parse import parse_qs

import httpx
import pytest

from app.services.accounting.quickbooks_client import INTUIT_API_BASE
from app.services.accounting.quickbooks_client import INTUIT_REVOKE_URL
from app.services.accounting.quickbooks_client import INTUIT_TOKEN_URL
from app.services.accounting.quickbooks_client import QuickBooksClient
from app.services.accounting.quickbooks_client import QuickBooksClientError
from app.services.accounting.quickbooks_client import QuickBooksConfigError
from app.services.accounting.quickbooks_client import (
    QuickBooksItemQuantityUpdateResult,
)
from app.services.accounting.quickbooks_client import QuickBooksItemSummary
from app.services.accounting.quickbooks_client import QuickBooksOAuthError
from app.services.accounting.quickbooks_client import QuickBooksRateLimitError
from app.services.accounting.quickbooks_client import TokenResult


CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret-XYZ"
REDIRECT = "https://app.example/callback"
TOKEN_OK = {
    "access_token": "AT-123",
    "refresh_token": "RT-456",
    "expires_in": 3600,
    "x_refresh_token_expires_in": 8726400,
    "token_type": "bearer",
    "scope": "com.intuit.quickbooks.accounting",
}


def _client(handler, **kw) -> QuickBooksClient:
    return QuickBooksClient(
        client_id=kw.pop("client_id", CLIENT_ID),
        client_secret=kw.pop("client_secret", CLIENT_SECRET),
        redirect_uri=kw.pop("redirect_uri", REDIRECT),
        transport=httpx.MockTransport(handler),
        **kw,
    )


# --------------------------------------------------------------------- #
# Construction / config
# --------------------------------------------------------------------- #


def test_missing_client_id_raises_config_error() -> None:
    with pytest.raises(QuickBooksConfigError):
        QuickBooksClient(client_id="", client_secret=CLIENT_SECRET)


def test_missing_client_secret_raises_config_error() -> None:
    with pytest.raises(QuickBooksConfigError) as exc:
        QuickBooksClient(client_id=CLIENT_ID, client_secret="")
    # Config error must not echo whichever credential WAS provided.
    assert CLIENT_ID not in str(exc.value)


def test_client_accepts_timeout_setting() -> None:
    # A hard timeout is accepted at construction and a request still completes.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=TOKEN_OK)

    client = _client(handler, timeout=3.0)
    assert client.exchange_code(code="abc").access_token == "AT-123"


# --------------------------------------------------------------------- #
# exchange_code
# --------------------------------------------------------------------- #


def test_exchange_code_request_shape_and_basic_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["ctype"] = request.headers.get("Content-Type")
        seen["form"] = parse_qs(request.content.decode("utf-8"))
        return httpx.Response(200, json=TOKEN_OK)

    _client(handler).exchange_code(code="the-auth-code", redirect_uri=REDIRECT)

    assert seen["url"] == INTUIT_TOKEN_URL
    assert seen["ctype"].startswith("application/x-www-form-urlencoded")
    assert seen["form"]["grant_type"] == ["authorization_code"]
    assert seen["form"]["code"] == ["the-auth-code"]
    assert seen["form"]["redirect_uri"] == [REDIRECT]
    # Basic auth carries the client id/secret — never logged, but sent.
    assert seen["auth"].startswith("Basic ")
    decoded = base64.b64decode(seen["auth"].split(" ", 1)[1]).decode("utf-8")
    assert decoded == f"{CLIENT_ID}:{CLIENT_SECRET}"


def test_exchange_code_parses_token_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=TOKEN_OK)

    result = _client(handler).exchange_code(code="abc")
    assert isinstance(result, TokenResult)
    assert result.access_token == "AT-123"
    assert result.refresh_token == "RT-456"
    assert result.token_type == "bearer"
    assert result.scopes == "com.intuit.quickbooks.accounting"
    now = datetime.now(UTC)
    assert result.access_token_expires_at > now
    assert result.refresh_token_expires_at is not None
    assert result.refresh_token_expires_at > result.access_token_expires_at


def test_exchange_code_oauth_error_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # invalid_grant — the body must NOT leak into the exception.
        return httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(QuickBooksOAuthError) as exc:
        _client(handler).exchange_code(code="the-auth-code")
    msg = str(exc.value)
    assert "400" in msg
    for leak in ("invalid_grant", "the-auth-code", CLIENT_SECRET, "Basic "):
        assert leak not in msg


def test_exchange_code_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "throttled"})

    with pytest.raises(QuickBooksRateLimitError) as exc:
        _client(handler).exchange_code(code="abc")
    assert "throttled" not in str(exc.value)


def test_exchange_code_missing_token_fields_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"token_type": "bearer"})

    with pytest.raises(QuickBooksClientError):
        _client(handler).exchange_code(code="abc")


def test_exchange_code_non_json_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(QuickBooksClientError):
        _client(handler).exchange_code(code="abc")


def test_exchange_code_transport_error_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom to localhost:1")

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler).exchange_code(code="the-auth-code")
    assert "the-auth-code" not in str(exc.value)
    assert CLIENT_SECRET not in str(exc.value)


# --------------------------------------------------------------------- #
# refresh_access_token
# --------------------------------------------------------------------- #


def test_refresh_request_shape_and_parse() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["form"] = parse_qs(request.content.decode("utf-8"))
        return httpx.Response(200, json=TOKEN_OK)

    result = _client(handler).refresh_access_token(refresh_token="RT-old")
    assert seen["form"]["grant_type"] == ["refresh_token"]
    assert seen["form"]["refresh_token"] == ["RT-old"]
    assert result.access_token == "AT-123"


def test_refresh_failure_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(QuickBooksOAuthError) as exc:
        _client(handler).refresh_access_token(refresh_token="RT-secret")
    msg = str(exc.value)
    assert "RT-secret" not in msg
    assert "invalid_grant" not in msg


# --------------------------------------------------------------------- #
# revoke_token
# --------------------------------------------------------------------- #


def test_revoke_success() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={})

    _client(handler).revoke_token(token="RT-456")
    assert seen["url"] == INTUIT_REVOKE_URL
    assert seen["auth"].startswith("Basic ")


def test_revoke_failure_is_controlled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_token"})

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler).revoke_token(token="RT-secret-token")
    msg = str(exc.value)
    assert "RT-secret-token" not in msg
    assert "invalid_token" not in msg


def test_revoke_transport_error_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler).revoke_token(token="RT-secret-token")
    assert "RT-secret-token" not in str(exc.value)


# --------------------------------------------------------------------- #
# list_items (F2.27.9.C) — read-only discovery
# --------------------------------------------------------------------- #


_ITEMS_OK = {
    "QueryResponse": {
        "Item": [
            {
                "Id": "1",
                "Name": "Widget",
                "Sku": "W-1",
                "Description": "A widget",
                "UnitPrice": 9.99,
                "PurchaseCost": 4.5,
                "QtyOnHand": 12,
            },
            {"Id": "2", "Name": "Gadget"},  # sparse: only id + name
        ],
        "maxResults": 2,
    },
    "time": "2026-06-09T00:00:00-07:00",
}


def test_list_items_parses_safe_summaries() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=_ITEMS_OK)

    items = _client(handler).list_items(
        access_token="AT-xyz", realm_id="REALM-1", environment="sandbox"
    )
    assert all(isinstance(i, QuickBooksItemSummary) for i in items)
    assert [i.external_item_id for i in items] == ["1", "2"]
    first = items[0]
    assert first.name == "Widget"
    assert first.sku == "W-1"
    assert first.unit_price == 9.99
    assert first.purchase_cost == 4.5
    assert first.quantity_on_hand == 12.0
    # Sparse item coerces missing fields to None (no crash).
    assert items[1].sku is None
    assert items[1].unit_price is None
    # Bearer access token used; query hits the sandbox data API + realm.
    assert seen["auth"] == "Bearer AT-xyz"
    assert seen["url"].startswith(
        f"{INTUIT_API_BASE['sandbox']}/v3/company/REALM-1/query"
    )


def test_list_items_uses_production_base_when_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(INTUIT_API_BASE["production"])
        return httpx.Response(200, json={"QueryResponse": {}})

    _client(handler).list_items(
        access_token="AT", realm_id="R", environment="production"
    )


def test_list_items_caps_at_max_items() -> None:
    payload = {
        "QueryResponse": {
            "Item": [{"Id": str(n)} for n in range(5)],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    items = _client(handler).list_items(
        access_token="AT", realm_id="R", max_items=2
    )
    assert len(items) == 2


def test_list_items_handles_empty_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"QueryResponse": {}, "time": "t"})

    assert _client(handler).list_items(access_token="AT", realm_id="R") == []


def test_list_items_error_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"Fault": {"type": "AUTHENTICATION"}})

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler).list_items(access_token="AT-secret", realm_id="R")
    msg = str(exc.value)
    assert "401" in msg
    for leak in ("AT-secret", CLIENT_SECRET, "AUTHENTICATION", "Bearer "):
        assert leak not in msg


def test_list_items_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "throttled"})

    with pytest.raises(QuickBooksRateLimitError):
        _client(handler).list_items(access_token="AT", realm_id="R")


def test_list_items_non_json_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html/>")

    with pytest.raises(QuickBooksClientError):
        _client(handler).list_items(access_token="AT", realm_id="R")


def test_list_items_transport_error_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler).list_items(access_token="AT-secret", realm_id="R")
    assert "AT-secret" not in str(exc.value)


# --------------------------------------------------------------------- #
# update_item_quantity (F2.27.9.D) — outbound, NubeRush-authoritative push
# --------------------------------------------------------------------- #


_NO_SLEEP = {"sleep": lambda _seconds: None}


def test_update_item_quantity_success_request_shape() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["ctype"] = request.headers.get("Content-Type")
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200, json={"Item": {"Id": "1", "SyncToken": "2", "QtyOnHand": 7}}
        )

    result = _client(handler).update_item_quantity(
        access_token="AT-xyz",
        realm_id="REALM-1",
        external_item_id="1",
        quantity_on_hand=7,
        environment="sandbox",
    )
    # Outbound write: POST to the item endpoint, sparse quantity update only.
    assert seen["method"] == "POST"
    assert seen["url"].startswith(
        f"{INTUIT_API_BASE['sandbox']}/v3/company/REALM-1/item"
    )
    assert seen["ctype"].startswith("application/json")
    assert seen["body"]["Id"] == "1"
    assert seen["body"]["QtyOnHand"] == 7.0
    assert seen["body"]["sparse"] is True
    assert seen["body"]["TrackQtyOnHand"] is True
    # Bearer access token ONLY in the Authorization header.
    assert seen["auth"] == "Bearer AT-xyz"
    assert isinstance(result, QuickBooksItemQuantityUpdateResult)
    assert result.pushed_quantity == 7.0
    # The QuickBooks echo is informational and stays in the backend result.
    assert result.quickbooks_quantity_on_hand == 7.0
    assert result.attempts == 1


def test_update_item_quantity_uses_bearer_only_no_secret_leak() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json={"Item": {"Id": "1"}})

    _client(handler).update_item_quantity(
        access_token="AT", realm_id="R", external_item_id="1",
        quantity_on_hand=3,
    )
    assert seen["headers"]["authorization"] == "Bearer AT"
    # The client secret never rides on an item write.
    assert CLIENT_SECRET not in str(seen["headers"])


def test_update_item_quantity_retries_on_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(
                429, headers={"Retry-After": "0"}, json={"error": "throttled"}
            )
        return httpx.Response(200, json={"Item": {"Id": "1"}})

    result = _client(handler, **_NO_SLEEP).update_item_quantity(
        access_token="AT", realm_id="R", external_item_id="1",
        quantity_on_hand=1, max_attempts=3,
    )
    assert calls["n"] == 3  # two 429 retries, then success
    assert result.attempts == 3


def test_update_item_quantity_429_exhausts_retries_raises_ratelimit() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": "throttled"})

    with pytest.raises(QuickBooksRateLimitError) as exc:
        _client(handler, **_NO_SLEEP).update_item_quantity(
            access_token="AT-secret", realm_id="R", external_item_id="1",
            quantity_on_hand=1, max_attempts=2,
        )
    assert calls["n"] == 2  # bounded: exactly max_attempts, no infinite loop
    msg = str(exc.value)
    assert "AT-secret" not in msg and "throttled" not in msg


def test_update_item_quantity_retries_on_5xx_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"Item": {"Id": "1"}})

    result = _client(handler, **_NO_SLEEP).update_item_quantity(
        access_token="AT", realm_id="R", external_item_id="1",
        quantity_on_hand=1, max_attempts=3,
    )
    assert calls["n"] == 2
    assert result.attempts == 2


def test_update_item_quantity_5xx_exhausts_retries_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="<html>upstream boom</html>")

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler, **_NO_SLEEP).update_item_quantity(
            access_token="AT-secret", realm_id="R", external_item_id="1",
            quantity_on_hand=1, max_attempts=2,
        )
    msg = str(exc.value)
    assert "500" in msg
    for leak in ("AT-secret", CLIENT_SECRET, "upstream boom", "Bearer "):
        assert leak not in msg


def test_update_item_quantity_4xx_not_retried_and_safe() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"Fault": {"type": "ValidationFault"}})

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler, **_NO_SLEEP).update_item_quantity(
            access_token="AT-secret", realm_id="R", external_item_id="1",
            quantity_on_hand=1, max_attempts=3,
        )
    assert calls["n"] == 1  # permanent 4xx is NOT retried
    msg = str(exc.value)
    assert "400" in msg
    for leak in ("AT-secret", CLIENT_SECRET, "ValidationFault", "Bearer "):
        assert leak not in msg


def test_update_item_quantity_transport_error_is_safe() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("boom to localhost:1")

    with pytest.raises(QuickBooksClientError) as exc:
        _client(handler, **_NO_SLEEP).update_item_quantity(
            access_token="AT-secret", realm_id="R", external_item_id="1",
            quantity_on_hand=1, max_attempts=2,
        )
    assert calls["n"] == 2  # transport error retried up to the cap
    assert "AT-secret" not in str(exc.value)


def test_update_item_quantity_clamps_hostile_retry_after() -> None:
    # A garbage / huge Retry-After must be clamped, never an unbounded wait.
    client = _client(lambda r: httpx.Response(200, json={}), **_NO_SLEEP)
    assert client._retry_delay_seconds("not-a-number", 0) >= 0
    assert client._retry_delay_seconds("100000", 0) <= 8.0
    assert client._retry_delay_seconds(None, 5) <= 8.0
