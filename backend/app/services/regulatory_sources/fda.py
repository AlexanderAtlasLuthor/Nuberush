"""FDA / public-regulatory-source parser (F2.27.7.A).

Maps a raw FDA (or FDA-shaped public regulatory) item dict onto a normalized,
matcher-compatible `ParsedNotice`. This module is pure: it performs no network
I/O, no DB access, requires no credentials, and makes no compliance decision.
It only turns one source-native dict into one value object.

Normalization responsibilities:
  - resolve the source identifier (`external_ref`) and require it + a title;
  - map the source's document type onto an existing `RegulatoryNoticeType`;
  - parse the publication date into a timezone-aware datetime;
  - remap source-native product field names (e.g. `upc`, `item_number`) onto
    the canonical `MATCHER_PRODUCT_KEYS` so the existing matching engine reads
    them unchanged, emitting a `products` list;
  - preserve a small, explicit allow-list of public metadata in `payload`
    (never the full raw item, no secrets, no full body text).

Anything not on the allow-list is dropped — the parser copies known fields
deliberately rather than passing the raw payload through.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Any

import httpx

from app.db.models import RegulatoryNoticeType
from app.services.regulatory_sources.base import RegulatorySourceFetchError
from app.services.regulatory_sources.base import RegulatorySourceParseError
from app.services.regulatory_sources.types import MATCHER_PRODUCT_KEYS
from app.services.regulatory_sources.types import ParsedNotice


# Tag this source's notices so a downstream reader can tell where the payload
# came from without consulting the (source-level) RegulatorySource row.
FDA_SOURCE_KIND: str = "fda"


# Source document types (normalized to a token) -> existing notice type. New
# document types extend this map; an unrecognized one is a clear parse error
# rather than a silent mis-bucketing.
_DOCUMENT_TYPE_TO_NOTICE_TYPE: dict[str, RegulatoryNoticeType] = {
    "enforcement_notice": RegulatoryNoticeType.enforcement_notice,
    "enforcement": RegulatoryNoticeType.enforcement_notice,
    "warning_letter": RegulatoryNoticeType.enforcement_notice,
    "advisory": RegulatoryNoticeType.advisory,
    "safety_communication": RegulatoryNoticeType.advisory,
    "authorized_product_list": RegulatoryNoticeType.authorized_product_list,
    "marketing_granted_order": RegulatoryNoticeType.authorized_product_list,
    "pmta_authorization": RegulatoryNoticeType.authorized_product_list,
    "retailer_guidance": RegulatoryNoticeType.retailer_guidance,
}


# Canonical matcher key -> source-native aliases (first non-empty wins). The
# canonical keys are exactly `MATCHER_PRODUCT_KEYS`.
_PRODUCT_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "product_name": ("product_name", "name", "product"),
    "brand": ("brand", "brand_name", "manufacturer"),
    "category": ("category", "product_category", "device_type"),
    "barcode": ("barcode", "upc", "upc_code", "gtin"),
    "sku": ("sku", "item_number", "item_no", "product_id"),
    "flavor": ("flavor", "flavour"),
}


def _clean_str(value: Any) -> str | None:
    """Return a trimmed string, or None for missing/blank/non-scalar input."""
    if value is None:
        return None
    if isinstance(value, bool):
        # A bool would str() to "True"/"False"; never a meaningful field value.
        return None
    text = str(value).strip()
    return text or None


def _clean_str_list(value: Any) -> list[str]:
    """Normalize a string or list-of-strings into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        cleaned = [_clean_str(item) for item in value]
        return [item for item in cleaned if item is not None]
    single = _clean_str(value)
    return [single] if single is not None else []


def _normalize_token(value: str) -> str:
    """Lowercase, collapse separators/whitespace to single underscores."""
    return "_".join(value.strip().lower().replace("-", " ").split())


def _map_notice_type(
    document_type: str, *, external_ref: str | None
) -> RegulatoryNoticeType:
    token = _normalize_token(document_type)
    notice_type = _DOCUMENT_TYPE_TO_NOTICE_TYPE.get(token)
    if notice_type is None:
        raise RegulatorySourceParseError(
            f"Unsupported FDA document_type {token!r}.",
            external_ref=external_ref,
        )
    return notice_type


def _parse_published_at(
    value: Any, *, external_ref: str | None
) -> datetime | None:
    """Parse an ISO date/datetime into a timezone-aware UTC datetime, or None.

    A naive value is assumed to be UTC. A present-but-unparseable value is a
    clear parse error rather than a silently dropped date.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _clean_str(value)
        if text is None:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise RegulatorySourceParseError(
                "Unparseable FDA publication date.",
                external_ref=external_ref,
            ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _normalize_product(raw_product: dict[str, Any]) -> dict[str, str]:
    """Remap one source product onto canonical matcher keys (present-only).

    A canonical key is included only when an aliased source value is non-empty,
    so a missing or blank field never appears (the matcher treats absent and
    blank fields identically, but a clean payload is easier to inspect).
    """
    normalized: dict[str, str] = {}
    for canonical_key in MATCHER_PRODUCT_KEYS:
        for alias in _PRODUCT_FIELD_ALIASES[canonical_key]:
            value = _clean_str(raw_product.get(alias))
            if value is not None:
                normalized[canonical_key] = value
                break
    return normalized


def _normalize_products(
    raw_products: Any, *, external_ref: str | None
) -> list[dict[str, str]]:
    """Normalize the raw `products` collection into matcher-compatible dicts.

    Absent products → empty list (a notice need not name a product). A present
    `products` that is not a list, or whose entries are not objects, is a
    malformed item and raises. Product dicts that yield no usable matcher field
    are dropped.
    """
    if raw_products is None:
        return []
    if not isinstance(raw_products, list):
        raise RegulatorySourceParseError(
            "FDA 'products' must be a list when present.",
            external_ref=external_ref,
        )
    products: list[dict[str, str]] = []
    for entry in raw_products:
        if not isinstance(entry, dict):
            raise RegulatorySourceParseError(
                "Each FDA product entry must be an object.",
                external_ref=external_ref,
            )
        normalized = _normalize_product(entry)
        if normalized:
            products.append(normalized)
    return products


def _build_payload(
    raw: dict[str, Any],
    *,
    external_ref: str,
    document_type_token: str,
    products: list[dict[str, str]],
) -> dict[str, Any]:
    """Assemble the matcher-compatible payload from an explicit allow-list.

    Only known public fields are copied — never the whole raw item, no secrets,
    no full body text. `products` (when present) carries the canonical matcher
    keys at the conventional path the matcher reads.
    """
    payload: dict[str, Any] = {
        "source_kind": FDA_SOURCE_KIND,
        "external_ref": external_ref,
        "document_type": document_type_token,
    }

    summary = _clean_str(raw.get("summary") or raw.get("description"))
    if summary is not None:
        payload["summary"] = summary

    company_name = _clean_str(raw.get("company_name") or raw.get("company"))
    if company_name is not None:
        payload["company_name"] = company_name

    tags = _clean_str_list(
        raw.get("categories") or raw.get("tags") or raw.get("raw_category")
    )
    if tags:
        payload["tags"] = tags

    published_source = _clean_str(
        raw.get("publication_date") or raw.get("published_at")
    )
    if published_source is not None:
        payload["published_source"] = published_source

    if products:
        payload["products"] = products

    return payload


def parse_fda_notice(raw: dict[str, Any]) -> ParsedNotice:
    """Parse one raw FDA/public regulatory item into a `ParsedNotice`.

    Pure and offline: no network, no DB, no credentials. Raises
    `RegulatorySourceParseError` (never an unhandled exception) on a malformed
    item — a missing identifier/title, an unsupported document type, a bad
    date, or a malformed `products` collection.
    """
    if not isinstance(raw, dict):
        raise RegulatorySourceParseError(
            "FDA source item must be a JSON object."
        )

    external_ref = _clean_str(
        raw.get("document_number")
        or raw.get("external_ref")
        or raw.get("id")
    )
    if external_ref is None:
        raise RegulatorySourceParseError(
            "FDA source item is missing a document identifier."
        )

    title = _clean_str(raw.get("title"))
    if title is None:
        raise RegulatorySourceParseError(
            "FDA source item is missing a title.",
            external_ref=external_ref,
        )

    document_type = _clean_str(
        raw.get("document_type") or raw.get("notice_type")
    )
    if document_type is None:
        raise RegulatorySourceParseError(
            "FDA source item is missing a document_type.",
            external_ref=external_ref,
        )
    document_type_token = _normalize_token(document_type)
    notice_type = _map_notice_type(document_type, external_ref=external_ref)

    published_at = _parse_published_at(
        raw.get("publication_date") or raw.get("published_at"),
        external_ref=external_ref,
    )
    source_url = _clean_str(raw.get("url") or raw.get("source_url"))
    products = _normalize_products(
        raw.get("products"), external_ref=external_ref
    )
    payload = _build_payload(
        raw,
        external_ref=external_ref,
        document_type_token=document_type_token,
        products=products,
    )

    return ParsedNotice(
        external_ref=external_ref,
        title=title,
        notice_type=notice_type,
        published_at=published_at,
        payload=payload,
        source_url=source_url,
    )


class FdaRegulatorySourceParser:
    """`RegulatorySourceParser` for FDA / public regulatory items.

    Stateless adapter around `parse_fda_notice` so the parser can be passed
    where the `RegulatorySourceParser` protocol is expected (e.g. the later
    orchestrator). Holds no configuration and performs no I/O.
    """

    source_kind: str = FDA_SOURCE_KIND

    def parse(self, raw: dict[str, Any]) -> ParsedNotice:
        return parse_fda_notice(raw)

    def parse_many(self, raws: list[dict[str, Any]]) -> list[ParsedNotice]:
        return [parse_fda_notice(raw) for raw in raws]


# Keys an FDA-shaped JSON document may wrap its item list under.
_ITEM_LIST_KEYS = ("results", "items", "data")


def _extract_items(data: Any, max_items: int) -> list[dict[str, Any]]:
    """Pull the raw item dicts out of an FDA-shaped JSON document.

    Accepts a bare list, or an object wrapping the list under `results` /
    `items` / `data`. Non-dict entries are dropped; the result is capped at
    `max_items` so a runaway feed can never blow up a single run.
    """
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = next(
            (
                value
                for key in _ITEM_LIST_KEYS
                if isinstance((value := data.get(key)), list)
            ),
            [],
        )
    else:
        items = []
    cleaned = [item for item in items if isinstance(item, dict)]
    if max_items and max_items > 0:
        return cleaned[:max_items]
    return cleaned


class FdaRegulatorySourceClient:
    """A real `RegulatorySourceClient` for an FDA / public regulatory JSON feed.

    Fetches one JSON document over HTTP(S) and returns its items as raw dicts
    for `FdaRegulatorySourceParser`. Secret-safe by construction (mirrors
    `app.services.supabase_admin`):
      - a hard timeout bounds every request;
      - an optional bearer API key is sent in the `Authorization` header and is
        NEVER logged, echoed, or stored;
      - any transport/HTTP/decoding failure raises a BARE
        `RegulatorySourceFetchError` — never the URL with its query, the key, or
        the response body;
      - the item list is capped at `max_items`.

    `transport` is injectable so tests drive it with `httpx.MockTransport`:
    there is NO real network in unit tests. In production it is left None and
    httpx opens a real connection.
    """

    def __init__(
        self,
        *,
        url: str,
        api_key: str | None = None,
        timeout: float = 10.0,
        max_items: int = 100,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._timeout = timeout
        self._max_items = max_items
        self._transport = transport

    def fetch(self) -> list[dict[str, Any]]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            with httpx.Client(
                transport=self._transport, timeout=self._timeout
            ) as client:
                response = client.get(self._url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            # Bare message: never echo the key, the URL with query, or the body.
            raise RegulatorySourceFetchError(
                "FDA regulatory source request failed."
            ) from exc
        except ValueError as exc:
            # Non-JSON body. Again, do not echo the body.
            raise RegulatorySourceFetchError(
                "FDA regulatory source returned a non-JSON body."
            ) from exc
        return _extract_items(data, self._max_items)
