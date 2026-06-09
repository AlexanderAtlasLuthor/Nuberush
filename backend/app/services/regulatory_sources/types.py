"""Typed, source-agnostic representation of a normalized regulatory notice
(F2.27.7.A).

`ParsedNotice` is the single output contract of every source parser in
`app.services.regulatory_sources`. It is a pure, in-memory value object: it
performs no I/O, touches no database, and carries no source binding (the
`source_id` is supplied later by the orchestrator that persists the notice,
F2.27.7.C — not by the parser).

Its `payload` is deliberately shaped to be matcher-compatible. The later
pipeline (`detect_regulatory_product_matches` in `app.services.regulatory`)
reads the keys named in `MATCHER_PRODUCT_KEYS`, either at the payload root or
inside a `products` list. Parsers MUST normalize external/source-specific
field names into these canonical keys so a parsed notice flows into the
existing matching engine unchanged — this subphase only produces the value,
it does not call that pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any

from app.db.models import RegulatoryNoticeType


# Canonical product/variant fields the regulatory matcher reads (mirrors
# `_PRODUCT_STRATEGIES` + `_VARIANT_STRATEGIES` in `app.services.regulatory`:
# product-level name/brand/category, variant-level barcode/sku/flavor). A
# parser normalizes source-specific field names into these so a ParsedNotice
# payload feeds the matcher without any adapter in between.
MATCHER_PRODUCT_KEYS: tuple[str, ...] = (
    "product_name",
    "brand",
    "category",
    "barcode",
    "sku",
    "flavor",
)


@dataclass(frozen=True, slots=True)
class ParsedNotice:
    """A normalized, source-agnostic regulatory notice ready for ingestion.

    Mirrors the fields `RegulatoryNoticeIngestRequest` needs MINUS `source_id`:
    binding a notice to a source is the orchestrator's job (F2.27.7.C), not the
    parser's. Frozen + slots: a parsed notice is an immutable value object.

    - `external_ref`  : the source's stable identifier for this notice (e.g. an
      FDA document number). Used downstream for dedupe; a parser SHOULD set it.
    - `title`         : human-readable notice title (required, non-empty).
    - `notice_type`   : an existing `RegulatoryNoticeType` enum member.
    - `published_at`  : timezone-aware publication datetime, or None.
    - `payload`       : free-form, JSON-safe data. Product identifiers inside it
      use the canonical `MATCHER_PRODUCT_KEYS`, at the root or under `products`.
    - `source_url`    : optional provenance URL the parser preserves when known.
    """

    external_ref: str | None
    title: str
    notice_type: RegulatoryNoticeType
    published_at: datetime | None
    payload: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
