"""Tests for the F2.27.7.A regulatory source client/parser abstraction.

Pure, offline, DB-free: these tests never request the `db_session` / `client`
fixtures, never open a socket, and need no credentials. They prove the FDA
parser normalizes a fixture into a matcher-compatible `ParsedNotice` and that
the abstraction (parser + in-memory client) composes without touching the
existing ingest/matching/alert pipeline.
"""

from __future__ import annotations

import inspect
import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.db.models import RegulatoryNoticeType
from app.services import regulatory as regulatory_svc
from app.services.regulatory_sources import FDA_SOURCE_KIND
from app.services.regulatory_sources import FdaRegulatorySourceParser
from app.services.regulatory_sources import MATCHER_PRODUCT_KEYS
from app.services.regulatory_sources import ParsedNotice
from app.services.regulatory_sources import RegulatorySourceParseError
from app.services.regulatory_sources import StaticRegulatorySourceClient
from app.services.regulatory_sources import parse_fda_notice


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fda_sample_notice.json"


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def raw_fda_item() -> dict[str, Any]:
    return _load_fixture()


@pytest.fixture
def parsed(raw_fda_item: dict[str, Any]) -> ParsedNotice:
    return parse_fda_notice(raw_fda_item)


# --------------------------------------------------------------------- #
# 1. Fixture parses into ParsedNotice
# --------------------------------------------------------------------- #


def test_fixture_parses_into_parsed_notice(parsed: ParsedNotice) -> None:
    assert isinstance(parsed, ParsedNotice)


# --------------------------------------------------------------------- #
# 2. external_ref is stable and non-empty
# --------------------------------------------------------------------- #


def test_external_ref_is_stable_and_non_empty(
    raw_fda_item: dict[str, Any], parsed: ParsedNotice
) -> None:
    assert parsed.external_ref == "FDA-2024-N-1234-0001"
    assert parsed.external_ref
    # Stable: parsing the same raw item again yields the same external_ref.
    assert parse_fda_notice(raw_fda_item).external_ref == parsed.external_ref


# --------------------------------------------------------------------- #
# 3. title is populated
# --------------------------------------------------------------------- #


def test_title_is_populated(parsed: ParsedNotice) -> None:
    assert parsed.title == (
        "FDA Issues Warning Letters to Firms for Selling "
        "Unauthorized E-Cigarettes"
    )


# --------------------------------------------------------------------- #
# 4. notice_type maps to the expected existing RegulatoryNoticeType
# --------------------------------------------------------------------- #


def test_notice_type_maps_to_existing_enum(parsed: ParsedNotice) -> None:
    assert parsed.notice_type is RegulatoryNoticeType.enforcement_notice


@pytest.mark.parametrize(
    ("document_type", "expected"),
    [
        ("enforcement_notice", RegulatoryNoticeType.enforcement_notice),
        ("Warning-Letter", RegulatoryNoticeType.enforcement_notice),
        ("safety communication", RegulatoryNoticeType.advisory),
        (
            "marketing_granted_order",
            RegulatoryNoticeType.authorized_product_list,
        ),
        ("retailer_guidance", RegulatoryNoticeType.retailer_guidance),
    ],
)
def test_document_type_token_mapping(
    document_type: str, expected: RegulatoryNoticeType
) -> None:
    raw = {
        "document_number": "X-1",
        "title": "t",
        "document_type": document_type,
    }
    assert parse_fda_notice(raw).notice_type is expected


# --------------------------------------------------------------------- #
# 5. published_at parses to a (tz-aware) datetime
# --------------------------------------------------------------------- #


def test_published_at_parses_to_datetime(parsed: ParsedNotice) -> None:
    assert isinstance(parsed.published_at, datetime)
    assert parsed.published_at == datetime(2024, 9, 15, tzinfo=UTC)
    assert parsed.published_at.tzinfo is not None


# --------------------------------------------------------------------- #
# 6. source_url is preserved
# --------------------------------------------------------------------- #


def test_source_url_is_preserved(parsed: ParsedNotice) -> None:
    assert parsed.source_url == (
        "https://www.fda.gov/tobacco-products/compliance-enforcement/"
        "example-enforcement-2024"
    )


# --------------------------------------------------------------------- #
# 7. payload contains products[]
# --------------------------------------------------------------------- #


def test_payload_contains_products_list(parsed: ParsedNotice) -> None:
    assert isinstance(parsed.payload.get("products"), list)
    assert len(parsed.payload["products"]) == 2


# --------------------------------------------------------------------- #
# 8. each product payload uses matcher-compatible keys
# --------------------------------------------------------------------- #


def test_products_use_matcher_compatible_keys(parsed: ParsedNotice) -> None:
    products = parsed.payload["products"]
    for product in products:
        assert set(product) <= set(MATCHER_PRODUCT_KEYS)
        # Every matcher key is present for the fully-specified fixture rows.
        assert set(product) == set(MATCHER_PRODUCT_KEYS)

    first = products[0]
    assert first["product_name"] == "Cloud Max Disposable 5000"
    assert first["brand"] == "CloudMax"
    assert first["category"] == "Disposable Vape"
    # Source-native aliases were remapped onto canonical matcher keys.
    assert first["barcode"] == "812345678901"  # from raw "upc"
    assert first["sku"] == "CM-DISP-5000"  # from raw "item_number"
    assert first["flavor"] == "Blue Razz Ice"


def test_matcher_keys_match_regulatory_strategy_contract() -> None:
    """Guard: our canonical keys equal exactly what the matcher reads.

    Cross-checks `MATCHER_PRODUCT_KEYS` against the payload keys the existing
    `detect_regulatory_product_matches` strategies consume, so the parser can
    never silently drift from the matcher contract.
    """
    product_keys = {key for _, key, _, _ in regulatory_svc._PRODUCT_STRATEGIES}
    variant_keys = {key for _, key, _, _ in regulatory_svc._VARIANT_STRATEGIES}
    assert set(MATCHER_PRODUCT_KEYS) == product_keys | variant_keys


# --------------------------------------------------------------------- #
# Payload metadata allow-list (public fields preserved, raw not dumped)
# --------------------------------------------------------------------- #


def test_payload_preserves_public_metadata(parsed: ParsedNotice) -> None:
    payload = parsed.payload
    assert payload["source_kind"] == FDA_SOURCE_KIND
    assert payload["external_ref"] == "FDA-2024-N-1234-0001"
    assert payload["document_type"] == "enforcement_notice"
    assert payload["company_name"] == "Example Vapor Co."
    assert payload["tags"] == ["ENDS", "Disposable", "Enforcement"]
    assert payload["published_source"] == "2024-09-15"
    assert "summary" in payload and payload["summary"]


# --------------------------------------------------------------------- #
# 9. parser requires no DB/session
# --------------------------------------------------------------------- #


def test_parser_requires_no_db_session() -> None:
    params = set(inspect.signature(parse_fda_notice).parameters)
    assert "db" not in params
    assert "session" not in params
    # And it produces a value with no DB available in this test at all.
    assert isinstance(parse_fda_notice(_load_fixture()), ParsedNotice)


# --------------------------------------------------------------------- #
# 10. parser performs no network calls
# --------------------------------------------------------------------- #


def test_parser_performs_no_network(
    raw_fda_item: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    def _blocked(*args: Any, **kwargs: Any):
        raise AssertionError("network access is forbidden in the parser")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)

    # Parsing and the in-memory client must complete with sockets blocked.
    parsed = parse_fda_notice(raw_fda_item)
    assert isinstance(parsed, ParsedNotice)

    client = StaticRegulatorySourceClient([raw_fda_item])
    parser = FdaRegulatorySourceParser()
    notices = parser.parse_many(client.fetch())
    assert len(notices) == 1
    assert notices[0].external_ref == parsed.external_ref


# --------------------------------------------------------------------- #
# 11. invalid / minimal payloads fail gracefully with a clear exception
# --------------------------------------------------------------------- #


def test_missing_identifier_raises() -> None:
    with pytest.raises(RegulatorySourceParseError):
        parse_fda_notice({"title": "t", "document_type": "advisory"})


def test_missing_title_raises() -> None:
    with pytest.raises(RegulatorySourceParseError) as exc_info:
        parse_fda_notice(
            {"document_number": "X-1", "document_type": "advisory"}
        )
    assert exc_info.value.external_ref == "X-1"


def test_unsupported_document_type_raises() -> None:
    with pytest.raises(RegulatorySourceParseError):
        parse_fda_notice(
            {
                "document_number": "X-1",
                "title": "t",
                "document_type": "totally_unknown_type",
            }
        )


def test_unparseable_published_date_raises() -> None:
    with pytest.raises(RegulatorySourceParseError):
        parse_fda_notice(
            {
                "document_number": "X-1",
                "title": "t",
                "document_type": "advisory",
                "publication_date": "not-a-date",
            }
        )


def test_malformed_products_collection_raises() -> None:
    with pytest.raises(RegulatorySourceParseError):
        parse_fda_notice(
            {
                "document_number": "X-1",
                "title": "t",
                "document_type": "advisory",
                "products": "not-a-list",
            }
        )


def test_non_object_raw_raises() -> None:
    with pytest.raises(RegulatorySourceParseError):
        parse_fda_notice(["not", "an", "object"])  # type: ignore[arg-type]


def test_parse_error_does_not_leak_raw_body() -> None:
    """The exception message must not embed the raw payload/body."""
    sentinel = "SENSITIVE-BODY-DO-NOT-LEAK-1234567890"
    raw = {
        "document_number": "X-9",
        "document_type": "advisory",
        "body": sentinel,
        "summary": sentinel,
        # title missing -> raises
    }
    with pytest.raises(RegulatorySourceParseError) as exc_info:
        parse_fda_notice(raw)
    assert sentinel not in str(exc_info.value)


# --------------------------------------------------------------------- #
# Minimal-but-valid + product normalization edge cases
# --------------------------------------------------------------------- #


def test_minimal_valid_item_without_products() -> None:
    parsed = parse_fda_notice(
        {
            "document_number": "X-2",
            "title": "Advisory with no named product",
            "document_type": "advisory",
        }
    )
    assert parsed.notice_type is RegulatoryNoticeType.advisory
    assert parsed.published_at is None
    assert parsed.source_url is None
    assert "products" not in parsed.payload


def test_product_with_no_usable_fields_is_dropped() -> None:
    parsed = parse_fda_notice(
        {
            "document_number": "X-3",
            "title": "t",
            "document_type": "advisory",
            "products": [
                {"unrelated_field": "ignored"},
                {"name": "Real Product"},
            ],
        }
    )
    products = parsed.payload["products"]
    assert len(products) == 1
    assert products[0] == {"product_name": "Real Product"}


def test_static_client_returns_isolated_copies(
    raw_fda_item: dict[str, Any]
) -> None:
    client = StaticRegulatorySourceClient([raw_fda_item])
    fetched = client.fetch()
    fetched[0]["title"] = "mutated"
    # Mutating a fetched copy never affects a subsequent fetch.
    assert client.fetch()[0]["title"] != "mutated"
