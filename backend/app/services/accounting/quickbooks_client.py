"""Secret-safe QuickBooks (Intuit) OAuth2 HTTP client (F2.27.9.B).

A small `httpx`-based client for the three OAuth token operations the connect /
callback / disconnect flow needs:

  - `exchange_code`        — authorization_code -> tokens
  - `refresh_access_token` — refresh_token -> new tokens
  - `revoke_token`         — best-effort revoke at disconnect

Secret-safe by construction (mirrors `app.services.supabase_admin` and
`app.services.regulatory_sources.fda`):

  - a hard timeout (from QuickBooks settings) bounds every request;
  - `client_id` / `client_secret` are server-only — sent only in the HTTP Basic
    `Authorization` header, NEVER logged, echoed, or placed in an exception;
  - every transport/HTTP/decoding failure raises a BARE error carrying at most
    an HTTP status code — never the access/refresh token, the OAuth `code`, the
    client secret, the `Authorization` header, the request form, or the raw
    Intuit response body;
  - `transport` is injectable so tests drive `httpx.MockTransport` — there is NO
    real network and NO real credentials in tests.

NO SDK and NO new dependency: only `httpx` (already a backend dependency) and
the stdlib. The returned `TokenResult` carries token MATERIAL and must stay
inside the backend service boundary — it is never serialized to an API schema.
"""
from __future__ import annotations

import base64
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import httpx


# Intuit OAuth2 endpoints. The token + revoke endpoints are environment-
# independent (sandbox and production share them); the sandbox vs production
# distinction only affects the Accounting API base used in a LATER subphase, not
# the OAuth handshake here.
INTUIT_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
INTUIT_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
INTUIT_REVOKE_URL = (
    "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
)

# Default accounting scope for the connect flow.
DEFAULT_SCOPE = "com.intuit.quickbooks.accounting"

# Accounting Data API base per environment. Unlike the OAuth endpoints above,
# the DATA API base DOES differ between sandbox and production. Used by
# `list_items` (read-only discovery); inventory writes are NOT implemented here.
INTUIT_API_BASE = {
    "sandbox": "https://sandbox-quickbooks.api.intuit.com",
    "production": "https://quickbooks.api.intuit.com",
}

# Bounded-retry policy for the single outbound write (`update_item_quantity`).
# 429 and 5xx are transient and retried; 4xx (other than 429) is a permanent
# rejection and is NOT retried. The cap is small and finite — there is NO
# scheduler, NO background retry, and NO infinite loop. Backoff honours an
# Intuit `Retry-After` header when present, otherwise a small exponential
# backoff, always clamped to `_RETRY_MAX_BACKOFF_SECONDS`.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_RETRY_BACKOFF_BASE_SECONDS = 0.5
_RETRY_MAX_BACKOFF_SECONDS = 8.0
_DEFAULT_UPDATE_MAX_ATTEMPTS = 3


def _coerce_number(value: object) -> float | None:
    """Best-effort numeric coercion for an Intuit money/qty field.

    Returns None for missing/unparseable values. Never raises and never echoes
    the value into an exception.
    """
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class QuickBooksClientError(Exception):
    """Base error for any QuickBooks client failure.

    The message is intentionally coarse and secret-free (an operation label and
    at most an HTTP status code). It never carries a token, the client secret,
    the `Authorization` header, the OAuth `code`, the request form, or the raw
    Intuit response body.
    """


class QuickBooksConfigError(QuickBooksClientError):
    """Raised when the client is constructed without client_id/client_secret."""


class QuickBooksOAuthError(QuickBooksClientError):
    """Raised when Intuit rejects an OAuth token request (4xx, e.g.
    invalid_grant). Carries the status code only, never the error body."""


class QuickBooksRateLimitError(QuickBooksClientError):
    """Raised when Intuit responds 429 Too Many Requests."""


@dataclass(frozen=True)
class TokenResult:
    """Internal, backend-only result of a token exchange/refresh.

    Carries token MATERIAL — it must NEVER cross an API schema boundary. The
    OAuth service encrypts `access_token` / `refresh_token` before any DB write.
    Expiry instants are computed from Intuit's relative `expires_in` /
    `x_refresh_token_expires_in` at the moment of the response.
    """

    access_token: str
    refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime | None
    scopes: str | None
    token_type: str | None


@dataclass(frozen=True)
class QuickBooksItemSummary:
    """A read-only, sanitized QuickBooks item summary for discovery/mapping.

    Carries ONLY the safe projection fields needed to map an external item to a
    NubeRush variant — never the raw Intuit payload. `quantity_on_hand` is
    informational only (NubeRush stays authoritative; nothing here mutates
    inventory).
    """

    external_item_id: str
    name: str | None
    sku: str | None
    description: str | None
    unit_price: float | None
    purchase_cost: float | None
    quantity_on_hand: float | None


@dataclass(frozen=True)
class QuickBooksItemQuantityUpdateResult:
    """Backend-only result of pushing a NubeRush quantity to a QuickBooks item.

    Outbound-only: `pushed_quantity` is the NubeRush-authoritative value we sent.
    `quickbooks_quantity_on_hand` is the value QuickBooks echoed back AFTER the
    write — informational only; the sync service NEVER writes it back into
    NubeRush. `sync_token` is QuickBooks' optimistic-concurrency token (not a
    secret) and stays inside the backend; it is never serialized to an API
    schema. Carries no token material, no auth header, and no raw Intuit body.
    """

    external_item_id: str
    pushed_quantity: float
    quickbooks_quantity_on_hand: float | None
    sync_token: str | None
    attempts: int


class QuickBooksClient:
    """Minimal Intuit OAuth2 client. Stateless apart from injected config.

    `transport` is injectable for `httpx.MockTransport` in tests; in production
    it is None and httpx opens a real connection bounded by `timeout`.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not client_id or not client_secret:
            # Never echo whichever value was provided.
            raise QuickBooksConfigError(
                "QuickBooks client is not configured "
                "(missing client id/secret)."
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout
        self._transport = transport
        # Injectable so tests drive bounded retries with a no-op sleep (no real
        # wall-clock delay, no real network).
        self._sleep = sleep

    # ----------------------------------------------------------------- #
    # Internal helpers
    # ----------------------------------------------------------------- #

    def _basic_auth_header(self) -> str:
        raw = f"{self._client_id}:{self._client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _post_token(self, form: dict[str, str]) -> dict:
        """POST to the Intuit token endpoint and return the parsed JSON.

        Raises a secret-free QuickBooks*Error on any failure; the message never
        contains the form (which holds the code / refresh token), the auth
        header, or the response body.
        """
        headers = {
            "Authorization": self._basic_auth_header(),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            with httpx.Client(
                transport=self._transport, timeout=self._timeout
            ) as client:
                response = client.post(
                    INTUIT_TOKEN_URL, headers=headers, data=form
                )
        except httpx.HTTPError as exc:
            raise QuickBooksClientError(
                "QuickBooks token request failed."
            ) from exc

        if response.status_code == 429:
            raise QuickBooksRateLimitError(
                "QuickBooks token request was rate limited (status 429)."
            )
        if response.status_code >= 400:
            # 4xx is typically an OAuth rejection (invalid_grant, etc.); 5xx is
            # an upstream fault. Either way, status code only — never the body.
            raise QuickBooksOAuthError(
                "QuickBooks token request was rejected "
                f"(status {response.status_code})."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise QuickBooksClientError(
                "QuickBooks token response was not valid JSON."
            ) from exc
        if not isinstance(data, dict):
            raise QuickBooksClientError(
                "QuickBooks token response had an unexpected shape."
            )
        return data

    def _to_token_result(self, data: dict) -> TokenResult:
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        if not access_token or not refresh_token:
            # Do not echo the partial body.
            raise QuickBooksClientError(
                "QuickBooks token response was missing token fields."
            )
        now = datetime.now(UTC)
        try:
            expires_in = int(data.get("expires_in", 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        access_expires_at = now + timedelta(seconds=expires_in)

        refresh_expires_at: datetime | None = None
        raw_refresh_ttl = data.get("x_refresh_token_expires_in")
        if raw_refresh_ttl is not None:
            try:
                refresh_expires_at = now + timedelta(
                    seconds=int(raw_refresh_ttl)
                )
            except (TypeError, ValueError):
                refresh_expires_at = None

        scope = data.get("scope")
        scopes = scope if isinstance(scope, str) and scope else None
        token_type = data.get("token_type")
        token_type = (
            token_type if isinstance(token_type, str) and token_type else None
        )
        return TokenResult(
            access_token=str(access_token),
            refresh_token=str(refresh_token),
            access_token_expires_at=access_expires_at,
            refresh_token_expires_at=refresh_expires_at,
            scopes=scopes,
            token_type=token_type,
        )

    # ----------------------------------------------------------------- #
    # Public operations
    # ----------------------------------------------------------------- #

    def exchange_code(
        self, *, code: str, redirect_uri: str | None = None
    ) -> TokenResult:
        """Exchange an authorization code for tokens."""
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or self._redirect_uri,
        }
        return self._to_token_result(self._post_token(form))

    def refresh_access_token(self, *, refresh_token: str) -> TokenResult:
        """Exchange a refresh token for a fresh access/refresh token pair."""
        form = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        return self._to_token_result(self._post_token(form))

    def revoke_token(self, *, token: str) -> None:
        """Best-effort revoke of an access or refresh token at Intuit.

        Raises a secret-free `QuickBooksClientError` on transport error or a
        non-2xx response. The caller treats revoke as best-effort and may
        swallow the error so a disconnect always completes locally.
        """
        headers = {
            "Authorization": self._basic_auth_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                transport=self._transport, timeout=self._timeout
            ) as client:
                response = client.post(
                    INTUIT_REVOKE_URL, headers=headers, json={"token": token}
                )
        except httpx.HTTPError as exc:
            raise QuickBooksClientError(
                "QuickBooks token revoke request failed."
            ) from exc

        if response.status_code not in (200, 204):
            raise QuickBooksClientError(
                "QuickBooks token revoke returned status "
                f"{response.status_code}."
            )

    def list_items(
        self,
        *,
        access_token: str,
        realm_id: str,
        environment: str = "sandbox",
        max_items: int = 100,
    ) -> list[QuickBooksItemSummary]:
        """Read-only discovery: return up to `max_items` QuickBooks items.

        Calls the Accounting Data API `query` endpoint with the Bearer
        access token. Returns SANITIZED summaries only — never the raw Intuit
        payload. Secret-safe: the access token rides only in the Authorization
        header (never logged), and any failure raises a bare error carrying at
        most an HTTP status code (never the token, the response body, or the
        query). NubeRush stays authoritative; this NEVER mutates inventory.
        """
        cap = max(0, int(max_items))
        base = INTUIT_API_BASE.get(environment, INTUIT_API_BASE["sandbox"])
        url = f"{base}/v3/company/{realm_id}/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        params = {"query": f"select * from Item maxresults {cap or 1}"}
        try:
            with httpx.Client(
                transport=self._transport, timeout=self._timeout
            ) as client:
                response = client.get(url, headers=headers, params=params)
        except httpx.HTTPError as exc:
            raise QuickBooksClientError(
                "QuickBooks item query request failed."
            ) from exc

        if response.status_code == 429:
            raise QuickBooksRateLimitError(
                "QuickBooks item query was rate limited (status 429)."
            )
        if response.status_code >= 400:
            raise QuickBooksClientError(
                "QuickBooks item query was rejected "
                f"(status {response.status_code})."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise QuickBooksClientError(
                "QuickBooks item query returned a non-JSON body."
            ) from exc

        raw_items = []
        if isinstance(data, dict):
            query_response = data.get("QueryResponse")
            if isinstance(query_response, dict):
                candidate = query_response.get("Item")
                if isinstance(candidate, list):
                    raw_items = candidate

        summaries: list[QuickBooksItemSummary] = []
        for raw in raw_items[:cap]:
            if not isinstance(raw, dict):
                continue
            external_id = raw.get("Id")
            if external_id is None or str(external_id) == "":
                continue
            summaries.append(
                QuickBooksItemSummary(
                    external_item_id=str(external_id),
                    name=raw.get("Name"),
                    sku=raw.get("Sku"),
                    description=raw.get("Description"),
                    unit_price=_coerce_number(raw.get("UnitPrice")),
                    purchase_cost=_coerce_number(raw.get("PurchaseCost")),
                    quantity_on_hand=_coerce_number(raw.get("QtyOnHand")),
                )
            )
        return summaries

    def _retry_delay_seconds(
        self, retry_after_header: str | None, attempt: int
    ) -> float:
        """Compute a clamped backoff delay for one retry.

        Honours an Intuit `Retry-After` header (seconds) when present and
        parseable; otherwise a small exponential backoff. Always clamped to
        `[0, _RETRY_MAX_BACKOFF_SECONDS]` so a hostile/garbage header can never
        cause an unbounded wait.
        """
        delay: float
        if retry_after_header is not None:
            try:
                delay = float(retry_after_header)
            except (TypeError, ValueError):
                delay = _RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
        else:
            delay = _RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
        if delay < 0:
            delay = 0.0
        return min(delay, _RETRY_MAX_BACKOFF_SECONDS)

    def update_item_quantity(
        self,
        *,
        access_token: str,
        realm_id: str,
        external_item_id: str,
        quantity_on_hand: float,
        sync_token: str | None = None,
        environment: str = "sandbox",
        max_attempts: int = _DEFAULT_UPDATE_MAX_ATTEMPTS,
    ) -> QuickBooksItemQuantityUpdateResult:
        """Push the NubeRush-authoritative `quantity_on_hand` to a mapped item.

        Outbound-only sparse update of an existing QuickBooks item's tracked
        quantity. This is the ONLY write the client performs — it never creates
        or deletes an item, and it NEVER reads QuickBooks quantity back into
        NubeRush.

        Secret-safe (mirrors `list_items`): the access token rides only in the
        `Authorization: Bearer` header (never logged); any failure raises a bare
        error carrying at most an HTTP status code — never the token, the client
        secret, the auth header, the request body, or the raw Intuit response
        body.

        Bounded retry: 429 (honouring `Retry-After`) and 5xx and transport/
        timeout errors are retried up to `max_attempts` with a small clamped
        backoff. A non-429 4xx is a permanent rejection and is NOT retried.
        There is NO background/scheduled retry and NO infinite loop.
        """
        if not external_item_id:
            raise QuickBooksClientError(
                "QuickBooks item update requires an item id."
            )
        attempts = max(1, int(max_attempts))
        base = INTUIT_API_BASE.get(environment, INTUIT_API_BASE["sandbox"])
        url = f"{base}/v3/company/{realm_id}/item"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        # Sparse update: touch ONLY the tracked quantity on the mapped item.
        # NubeRush is authoritative; this mirrors our quantity outbound.
        body = {
            "Id": str(external_item_id),
            "SyncToken": str(sync_token) if sync_token is not None else "0",
            "sparse": True,
            "TrackQtyOnHand": True,
            "QtyOnHand": float(quantity_on_hand),
        }

        for attempt in range(attempts):
            is_last = attempt + 1 >= attempts
            try:
                with httpx.Client(
                    transport=self._transport, timeout=self._timeout
                ) as client:
                    response = client.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                # Transport/timeout — retry up to the cap, then a bare error.
                if is_last:
                    raise QuickBooksClientError(
                        "QuickBooks item update request failed."
                    ) from exc
                self._sleep(self._retry_delay_seconds(None, attempt))
                continue

            status_code = response.status_code
            if status_code in _RETRYABLE_STATUS:
                if is_last:
                    if status_code == 429:
                        raise QuickBooksRateLimitError(
                            "QuickBooks item update was rate limited "
                            "(status 429)."
                        )
                    raise QuickBooksClientError(
                        "QuickBooks item update failed after retries "
                        f"(status {status_code})."
                    )
                self._sleep(
                    self._retry_delay_seconds(
                        response.headers.get("Retry-After"), attempt
                    )
                )
                continue
            if status_code >= 400:
                # Permanent rejection: status code only, never the body.
                raise QuickBooksClientError(
                    "QuickBooks item update was rejected "
                    f"(status {status_code})."
                )

            # Success: parse a minimal, sanitized result — never the raw payload.
            new_sync_token: str | None = None
            new_qty: float | None = None
            try:
                data = response.json()
            except ValueError:
                data = None
            if isinstance(data, dict):
                item = data.get("Item")
                if isinstance(item, dict):
                    token_val = item.get("SyncToken")
                    new_sync_token = (
                        str(token_val) if token_val is not None else None
                    )
                    new_qty = _coerce_number(item.get("QtyOnHand"))
            return QuickBooksItemQuantityUpdateResult(
                external_item_id=str(external_item_id),
                pushed_quantity=float(quantity_on_hand),
                quickbooks_quantity_on_hand=new_qty,
                sync_token=new_sync_token,
                attempts=attempt + 1,
            )

        # Defensive: the loop always returns or raises within `attempts`.
        raise QuickBooksClientError("QuickBooks item update failed.")
