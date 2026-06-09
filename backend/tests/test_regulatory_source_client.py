"""Tests for the real FDA/public source HTTP client boundary (F2.27.7.D).

Drives `FdaRegulatorySourceClient` with `httpx.MockTransport` — there is NO
real network and NO credentials. Verifies item extraction/capping, the
optional bearer header, and that any transport/HTTP/decoding failure raises a
BARE `RegulatorySourceFetchError` that leaks no URL/key/body. Also checks the
orchestrator's `resolve_source_client` builds the client from non-secret
`fetch_config["url"]` and raises a controlled error when no URL is configured.
"""
from __future__ import annotations

import httpx
import pytest

from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
from app.services import regulatory_ingestion as ing
from app.services.regulatory_sources import FdaRegulatorySourceClient
from app.services.regulatory_sources import RegulatorySourceFetchError


def _client(handler, **kw) -> FdaRegulatorySourceClient:
    return FdaRegulatorySourceClient(
        url="https://example.test/feed",
        transport=httpx.MockTransport(handler),
        **kw,
    )


def test_fetch_returns_list_of_dicts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"a": 1}, {"b": 2}])

    assert _client(handler).fetch() == [{"a": 1}, {"b": 2}]


@pytest.mark.parametrize("key", ["results", "items", "data"])
def test_fetch_extracts_wrapper_key(key: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={key: [{"x": 1}]})

    assert _client(handler).fetch() == [{"x": 1}]


def test_fetch_drops_non_dicts_and_caps_max_items() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[{"a": 1}, {"b": 2}, {"c": 3}, "skip", 5]
        )

    assert _client(handler, max_items=2).fetch() == [{"a": 1}, {"b": 2}]


def test_fetch_sends_bearer_when_api_key_present() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=[])

    _client(handler, api_key="SECRET-KEY").fetch()
    assert seen["auth"] == "Bearer SECRET-KEY"


def test_fetch_no_auth_header_without_key() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=[])

    _client(handler).fetch()
    assert seen["auth"] is None


def test_http_error_raises_bare_fetch_error_without_leaks() -> None:
    leaky_url = "https://example.test/feed?api_key=LEAKME-TOKEN-123"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server boom body with secrets")

    client = FdaRegulatorySourceClient(
        url=leaky_url, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RegulatorySourceFetchError) as exc_info:
        client.fetch()
    message = str(exc_info.value)
    assert "LEAKME-TOKEN-123" not in message
    assert "api_key" not in message
    assert "server boom body" not in message


def test_non_json_body_raises_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(RegulatorySourceFetchError):
        _client(handler).fetch()


def test_transport_error_raises_bare_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused to secret-host:443")

    with pytest.raises(RegulatorySourceFetchError) as exc_info:
        _client(handler).fetch()
    assert "secret-host" not in str(exc_info.value)


def test_client_opens_no_real_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("real network is forbidden")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"a": 1}])

    assert _client(handler).fetch() == [{"a": 1}]


# --------------------------------------------------------------------- #
# resolve_source_client wiring (no DB needed — in-memory source)
# --------------------------------------------------------------------- #


def test_resolve_builds_client_from_fetch_config_url() -> None:
    source = RegulatorySource(
        name="s",
        kind=RegulatorySourceKind.fda_enforcement,
        fetch_config={"url": "https://example.test/feed"},
    )
    client = ing.resolve_source_client(source)
    assert isinstance(client, FdaRegulatorySourceClient)


def test_resolve_raises_controlled_error_without_url() -> None:
    source = RegulatorySource(
        name="s", kind=RegulatorySourceKind.fda_enforcement
    )
    with pytest.raises(ing.RegulatorySourceIngestionError):
        ing.resolve_source_client(source)
