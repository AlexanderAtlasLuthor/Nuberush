"""Service layer for regulatory sources, ingestion, matching, alerts +
resolution (F2.26.5.B + .C + .D).

This module owns the backend-first, human-driven Regulatory Intelligence
Foundation:
  - registering/listing regulatory sources (B);
  - manually ingesting notices with stable, dedupe-able content hashes (B);
  - detecting best-effort matches between a notice payload and internal
    products/variants (C);
  - generating human-reviewable `compliance_alerts` from those matches and
    running the admin-reviewed alert lifecycle (acknowledge / dismiss /
    resolve), writing `regulatory_decision_audit_logs` for every decision (D).

A match and an alert are BEST-EFFORT and ADVISORY. Creating an alert NEVER
changes product sellability. Only an explicit `resolve` with action `hold` or
`ban` applies a real compliance change — and it does so EXCLUSIVELY by
delegating to the existing `set_product_compliance()` service, which owns the
Product mutation, the `product_compliance_audit_logs` row, and the
ban→inventory-quarantine cascade.

Deliberately NOT in this module:
  - any DIRECT write to Product compliance/sellability/approval fields — those
    flow only through `set_product_compliance()`;
  - any DIRECT Inventory mutation — the ban cascade is owned by
    `set_product_compliance()`, not here;
  - any `operational_audit_logs` write (regulatory decisions use the dedicated
    `regulatory_decision_audit_logs` table);
  - external HTTP fetch, scraping, schedulers/cron, notifications, routes,
    auto-block/hold/ban (every compliance change is admin-initiated).

`set_product_compliance` is referenced as a module attribute so it can be
spied in tests; matching/alert-creation never call it.

Conventions (consistent with `app.services.stores` / `app.services.users`):
  - Each function takes a `Session` first and owns its own commit/rollback;
    routers do not need to catch `IntegrityError` — this layer translates it
    to HTTP 422.
  - Missing lookups raise HTTP 404; bad pagination raises HTTP 422.
  - RBAC is intentionally NOT enforced here. There are no routes in F2.26.5.B;
    the (future) admin route layer threads authorization, mirroring how the
    operational-audit writer stays caller-agnostic.

Ingestion is idempotent on `(source_id, content_hash)`: re-ingesting the same
semantic content returns the existing notice instead of creating a duplicate.
The dedupe is order-insensitive because the hash canonicalizes the payload
JSON with sorted keys.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryMatchStrategy
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryNoticeType
from app.db.models import RegulatoryProductMatch
from app.db.models import RegulatorySource
from app.db.models import User
from app.schemas.products import ProductComplianceUpdate
from app.schemas.regulatory import ComplianceAlertActionRequest
from app.schemas.regulatory import ComplianceAlertListResponse
from app.schemas.regulatory import ComplianceAlertRead
from app.schemas.regulatory import ComplianceAlertResolutionAction
from app.schemas.regulatory import ComplianceAlertResolveRequest
from app.schemas.regulatory import RegulatoryDecisionAction
from app.schemas.regulatory import RegulatoryDecisionAuditLogListResponse
from app.schemas.regulatory import RegulatoryDecisionAuditLogRead
from app.schemas.regulatory import RegulatoryNoticeIngestRequest
from app.schemas.regulatory import RegulatoryNoticeListResponse
from app.schemas.regulatory import RegulatoryNoticeRead
from app.schemas.regulatory import RegulatoryProductMatchRead
from app.schemas.regulatory import RegulatorySourceCreate
from app.schemas.regulatory import RegulatorySourceListResponse
from app.schemas.regulatory import RegulatorySourceRead
from app.services.products import set_product_compliance


_MAX_LIST_LIMIT = 100


def _assert_list_pagination(limit: int, offset: int) -> None:
    if limit < 1 or limit > _MAX_LIST_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"limit must be between 1 and {_MAX_LIST_LIMIT}.",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be greater than or equal to 0.",
        )


# --------------------------------------------------------------------- #
# Content hash
# --------------------------------------------------------------------- #


def compute_regulatory_notice_content_hash(
    *,
    notice_type: RegulatoryNoticeType | str,
    title: str,
    external_ref: str | None,
    published_at: datetime | None,
    payload: dict[str, Any],
) -> str:
    """Compute a stable, order-insensitive SHA-256 content hash for a notice.

    The hash participates in the `(source_id, content_hash)` dedupe. It is
    deterministic across runs and across equivalent JSON orderings:

    - the payload (and every nested dict) is serialized with `sort_keys=True`
      and compact separators, so re-ordering keys does not change the hash;
    - the discriminating notice metadata (`notice_type`, `title`,
      `external_ref`, `published_at`) is folded in so two snapshots that share
      a payload but differ in metadata hash differently;
    - `notice_type` is normalized to its enum value, `published_at` to ISO
      8601, and any non-JSON-native leaf (e.g. Decimal) falls back to `str`.

    Note `source_id` is intentionally NOT part of the hash: scoping is the
    `(source_id, content_hash)` pair, so identical content under two sources
    correctly yields two distinct notices.
    """
    canonical = {
        "notice_type": getattr(notice_type, "value", notice_type),
        "title": title,
        "external_ref": external_ref,
        "published_at": (
            published_at.isoformat() if published_at is not None else None
        ),
        "payload": payload,
    }
    blob = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- #
# Regulatory source service
# --------------------------------------------------------------------- #


def create_regulatory_source(
    db: Session, payload: RegulatorySourceCreate
) -> RegulatorySourceRead:
    """Register a regulatory source.

    `name` is unique at the DB layer; a duplicate surfaces as HTTP 422 via
    IntegrityError translation with a clean rollback. `is_active` defaults to
    True (schema + model default); an inactive source can be created by
    passing `is_active=False`. No sync is performed — `last_synced_at` stays
    NULL until a future ingestion phase sets it.
    """
    source = RegulatorySource(
        name=payload.name,
        kind=payload.kind,
        reference_url=payload.reference_url,
        is_active=payload.is_active,
    )
    db.add(source)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Regulatory source violates database constraints.",
        ) from exc
    db.refresh(source)
    return RegulatorySourceRead.model_validate(source)


def get_regulatory_source(
    db: Session, source_id: UUID
) -> RegulatorySource:
    """Fetch a regulatory source or raise 404.

    Returns the ORM row (mirrors `app.services.stores.get_store`) so callers
    — including `ingest_regulatory_notice` — can use it directly.
    """
    source = db.get(RegulatorySource, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regulatory source not found.",
        )
    return source


def list_regulatory_sources(
    db: Session,
    *,
    limit: int = 25,
    offset: int = 0,
    is_active: bool | None = None,
) -> RegulatorySourceListResponse:
    """Paginated list of regulatory sources.

    `is_active=None` means "any state". Sort is `created_at DESC` with
    `id ASC` as a stable tie-breaker. `total` is computed before pagination.
    """
    _assert_list_pagination(limit, offset)

    stmt = select(RegulatorySource)
    count_stmt = select(func.count()).select_from(RegulatorySource)

    if is_active is not None:
        stmt = stmt.where(RegulatorySource.is_active.is_(is_active))
        count_stmt = count_stmt.where(
            RegulatorySource.is_active.is_(is_active)
        )

    stmt = stmt.order_by(
        RegulatorySource.created_at.desc(), RegulatorySource.id.asc()
    )
    stmt = stmt.limit(limit).offset(offset)

    rows = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0

    return RegulatorySourceListResponse(
        items=[RegulatorySourceRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------- #
# Regulatory notice ingestion service
# --------------------------------------------------------------------- #


def _find_notice_by_hash(
    db: Session, source_id: UUID, content_hash: str
) -> RegulatoryNotice | None:
    return db.scalar(
        select(RegulatoryNotice).where(
            RegulatoryNotice.source_id == source_id,
            RegulatoryNotice.content_hash == content_hash,
        )
    )


def ingest_regulatory_notice(
    db: Session, payload: RegulatoryNoticeIngestRequest
) -> RegulatoryNoticeRead:
    """Manually ingest a regulatory notice, idempotent on content hash.

    Steps:
      1. Validate the source exists (404 otherwise).
      2. Compute a stable, order-insensitive `content_hash`.
      3. If a notice with the same `(source_id, content_hash)` already exists,
         return it unchanged — no duplicate row is created.
      4. Otherwise persist the new notice (raw payload preserved verbatim) and
         return it.

    This is pure persistence: it queries no products, creates no matches or
    alerts, writes no audit rows, and mutates no Product/Inventory state.

    The unique `(source_id, content_hash)` index is the final arbiter — if a
    concurrent ingest wins the race between our existence check and insert, the
    resulting IntegrityError is caught and the now-committed existing row is
    returned, keeping the operation idempotent under concurrency.
    """
    # 1. Source must exist (clear 404 rather than an FK IntegrityError).
    get_regulatory_source(db, payload.source_id)

    # 2. Stable content hash.
    content_hash = compute_regulatory_notice_content_hash(
        notice_type=payload.notice_type,
        title=payload.title,
        external_ref=payload.external_ref,
        published_at=payload.published_at,
        payload=payload.payload,
    )

    # 3. Dedupe: reuse an existing notice for this (source, hash).
    existing = _find_notice_by_hash(db, payload.source_id, content_hash)
    if existing is not None:
        return RegulatoryNoticeRead.model_validate(existing)

    # 4. Persist the new notice.
    notice = RegulatoryNotice(
        source_id=payload.source_id,
        external_ref=payload.external_ref,
        title=payload.title,
        notice_type=payload.notice_type,
        published_at=payload.published_at,
        payload=payload.payload,
        content_hash=content_hash,
    )
    db.add(notice)
    try:
        db.commit()
    except IntegrityError as exc:
        # A concurrent ingest committed the same (source_id, content_hash)
        # between our check and this insert. Roll back and reuse that row so
        # ingestion stays idempotent.
        db.rollback()
        raced = _find_notice_by_hash(db, payload.source_id, content_hash)
        if raced is not None:
            return RegulatoryNoticeRead.model_validate(raced)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Regulatory notice violates database constraints.",
        ) from exc
    db.refresh(notice)
    return RegulatoryNoticeRead.model_validate(notice)


# --------------------------------------------------------------------- #
# Product matching (F2.26.5.C)
# --------------------------------------------------------------------- #
#
# Best-effort, advisory matching of a notice's payload against the internal
# catalog. Persists `regulatory_product_matches` ONLY — it reads Product /
# ProductVariant but never writes them, and touches no alert / decision-audit
# / operational-audit / inventory state.


# Product-level strategies: (enum, payload key, Product attribute, confidence).
_PRODUCT_STRATEGIES: tuple[
    tuple[RegulatoryMatchStrategy, str, str, Decimal], ...
] = (
    (RegulatoryMatchStrategy.name, "product_name", "name", Decimal("0.90")),
    (RegulatoryMatchStrategy.brand, "brand", "brand", Decimal("0.70")),
    (RegulatoryMatchStrategy.category, "category", "category", Decimal("0.50")),
)

# Variant-level strategies: (enum, payload key, ProductVariant attr, confidence).
_VARIANT_STRATEGIES: tuple[
    tuple[RegulatoryMatchStrategy, str, str, Decimal], ...
] = (
    (RegulatoryMatchStrategy.barcode, "barcode", "barcode", Decimal("1.00")),
    (RegulatoryMatchStrategy.sku, "sku", "sku", Decimal("0.95")),
    (RegulatoryMatchStrategy.flavor, "flavor", "flavor", Decimal("0.60")),
)


def normalize_match_value(value: Any) -> str | None:
    """Deterministic normalization for match comparison.

    Trims, collapses internal whitespace runs to a single space, and casefolds
    for case-insensitive equality. Returns None for None / non-string-coercible
    empties so a missing or blank field never participates in a match.

    Applied uniformly to every strategy (name/brand/category/sku/barcode/
    flavor). Barcodes and SKUs carry no internal whitespace in practice, so the
    collapse is a no-op for them; casefolding a numeric barcode is harmless.
    Punctuation is preserved — only whitespace and case are normalized.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split()).casefold()


def _parse_payload_items(
    payload: dict[str, Any],
) -> list[tuple[dict[str, Any], str | None]]:
    """Extract the list of (item, payload_path_prefix) to match against.

    Conservative shape support:
      - if `payload["products"]` is a list, each dict element is one item with
        prefix `products[i]`;
      - otherwise the payload root itself is treated as a single item
        (prefix None → field paths are the bare key names).

    The two shapes are mutually exclusive (a `products` list wins) so a single
    payload can never be counted twice.
    """
    if not isinstance(payload, dict):
        return []
    products = payload.get("products")
    if isinstance(products, list):
        return [
            (item, f"products[{i}]")
            for i, item in enumerate(products)
            if isinstance(item, dict)
        ]
    return [(payload, None)]


def _payload_path(prefix: str | None, key: str) -> str:
    return key if prefix is None else f"{prefix}.{key}"


def detect_regulatory_product_matches(
    db: Session, notice_id: UUID
) -> list[RegulatoryProductMatchRead]:
    """Detect + persist best-effort matches for a regulatory notice.

    Reads the notice payload, compares its values against the internal catalog
    on the six existing-field strategies (name/brand/category at the product
    level; sku/barcode/flavor at the variant level), and persists one
    `RegulatoryProductMatch` per distinct
    `(product_id, variant_id, match_strategy)` triple.

    Idempotent and dedupe-safe at the SERVICE level (not relying on the DB
    unique index, which does not dedupe product-level rows where
    `variant_id IS NULL` because Postgres treats NULLs as distinct):
      - existing matches for the notice are loaded and reused, never recreated;
      - duplicate payload values collapse to a single row within a run;
      - a second detection run creates nothing new.

    Returns every match for the notice (reused + newly created). Purely
    additive: no Product/Variant/Inventory/alert/audit write occurs.
    """
    notice = db.get(RegulatoryNotice, notice_id)
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regulatory notice not found.",
        )

    items = _parse_payload_items(notice.payload or {})

    # Build normalized catalog indexes once. Matching spans the whole catalog
    # (active and inactive) because regulatory relevance does not depend on
    # sellability.
    products = list(db.scalars(select(Product)).all())
    variants = list(db.scalars(select(ProductVariant)).all())

    product_index: dict[str, dict[str, list[Product]]] = {
        attr: defaultdict(list) for _, _, attr, _ in _PRODUCT_STRATEGIES
    }
    for product in products:
        for _, _, attr, _ in _PRODUCT_STRATEGIES:
            norm = normalize_match_value(getattr(product, attr))
            if norm is not None:
                product_index[attr][norm].append(product)

    variant_index: dict[str, dict[str, list[ProductVariant]]] = {
        attr: defaultdict(list) for _, _, attr, _ in _VARIANT_STRATEGIES
    }
    for variant in variants:
        for _, _, attr, _ in _VARIANT_STRATEGIES:
            norm = normalize_match_value(getattr(variant, attr))
            if norm is not None:
                variant_index[attr][norm].append(variant)

    # Existing matches for this notice seed the dedupe set so re-runs are
    # idempotent. Key is (product_id, variant_id, strategy); variant_id may be
    # None (the case the DB index cannot dedupe).
    existing = list(
        db.scalars(
            select(RegulatoryProductMatch).where(
                RegulatoryProductMatch.notice_id == notice_id
            )
        ).all()
    )
    seen: set[tuple[UUID, UUID | None, RegulatoryMatchStrategy]] = {
        (m.product_id, m.variant_id, m.match_strategy) for m in existing
    }

    new_matches: list[RegulatoryProductMatch] = []

    for item, prefix in items:
        # Product-level strategies.
        for strategy, key, attr, confidence in _PRODUCT_STRATEGIES:
            if key not in item:
                continue
            raw = item[key]
            norm = normalize_match_value(raw)
            if norm is None:
                continue
            for product in product_index[attr].get(norm, ()):
                dedupe_key = (product.id, None, strategy)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                new_matches.append(
                    RegulatoryProductMatch(
                        notice_id=notice_id,
                        product_id=product.id,
                        variant_id=None,
                        match_strategy=strategy,
                        confidence=confidence,
                        matched_fields={
                            "strategy": strategy.value,
                            "notice_value": str(raw),
                            "catalog_value": getattr(product, attr),
                            "payload_path": _payload_path(prefix, key),
                        },
                    )
                )

        # Variant-level strategies.
        for strategy, key, attr, confidence in _VARIANT_STRATEGIES:
            if key not in item:
                continue
            raw = item[key]
            norm = normalize_match_value(raw)
            if norm is None:
                continue
            for variant in variant_index[attr].get(norm, ()):
                dedupe_key = (variant.product_id, variant.id, strategy)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                new_matches.append(
                    RegulatoryProductMatch(
                        notice_id=notice_id,
                        product_id=variant.product_id,
                        variant_id=variant.id,
                        match_strategy=strategy,
                        confidence=confidence,
                        matched_fields={
                            "strategy": strategy.value,
                            "notice_value": str(raw),
                            "catalog_value": getattr(variant, attr),
                            "payload_path": _payload_path(prefix, key),
                        },
                    )
                )

    if new_matches:
        db.add_all(new_matches)
        try:
            db.commit()
        except IntegrityError as exc:
            # A concurrent detection run persisted overlapping rows between our
            # read and commit. Roll back and fall through to a fresh read so
            # the result reflects the committed set (idempotent under races).
            db.rollback()
            current = list(
                db.scalars(
                    select(RegulatoryProductMatch).where(
                        RegulatoryProductMatch.notice_id == notice_id
                    )
                ).all()
            )
            if current:
                return [
                    RegulatoryProductMatchRead.model_validate(m)
                    for m in current
                ]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Regulatory product match violates database "
                "constraints.",
            ) from exc
        for match in new_matches:
            db.refresh(match)

    return [
        RegulatoryProductMatchRead.model_validate(m)
        for m in (*existing, *new_matches)
    ]


# --------------------------------------------------------------------- #
# Compliance alerts + admin-reviewed resolution (F2.26.5.D)
# --------------------------------------------------------------------- #
#
# Alert generation is advisory: it never mutates a product or inventory and
# writes no decision audit. Only an explicit resolve(hold|ban) applies a real
# compliance change, and ONLY via `set_product_compliance()`.


# Per-strategy alert policy: strategy -> (severity, recommended_action).
# High-signal identity matches (barcode/sku/name) recommend a review hold;
# weaker matches are informational (recommended_action = none).
_ALERT_POLICY: dict[
    RegulatoryMatchStrategy,
    tuple[ComplianceAlertSeverity, ComplianceRecommendedAction],
] = {
    RegulatoryMatchStrategy.barcode: (
        ComplianceAlertSeverity.high,
        ComplianceRecommendedAction.hold,
    ),
    RegulatoryMatchStrategy.sku: (
        ComplianceAlertSeverity.high,
        ComplianceRecommendedAction.hold,
    ),
    RegulatoryMatchStrategy.name: (
        ComplianceAlertSeverity.high,
        ComplianceRecommendedAction.hold,
    ),
    RegulatoryMatchStrategy.brand: (
        ComplianceAlertSeverity.medium,
        ComplianceRecommendedAction.none,
    ),
    RegulatoryMatchStrategy.category: (
        ComplianceAlertSeverity.low,
        ComplianceRecommendedAction.none,
    ),
    RegulatoryMatchStrategy.flavor: (
        ComplianceAlertSeverity.low,
        ComplianceRecommendedAction.none,
    ),
}

# Terminal alert statuses — no further lifecycle action is permitted.
_TERMINAL_ALERT_STATUSES = (
    ComplianceAlertStatus.actioned,
    ComplianceAlertStatus.dismissed,
)


def create_compliance_alerts_from_matches(
    db: Session, notice_id: UUID
) -> list[ComplianceAlertRead]:
    """Generate human-reviewable compliance alerts from a notice's matches.

    One `ComplianceAlert` is created per `RegulatoryProductMatch` (carrying its
    `match_id` and `product_id`), starting `status=open` with a deterministic
    `severity` + conservative `recommended_action` from `_ALERT_POLICY`.

    Idempotent: existing alerts (keyed by `match_id`) are reused, so re-running
    creates no duplicates. Purely advisory — NO product/inventory mutation, NO
    `set_product_compliance()` call, NO decision-audit / compliance-audit /
    operational-audit write. Returns every alert for the notice (reused + new).
    """
    notice = db.get(RegulatoryNotice, notice_id)
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regulatory notice not found.",
        )

    matches = list(
        db.scalars(
            select(RegulatoryProductMatch).where(
                RegulatoryProductMatch.notice_id == notice_id
            )
        ).all()
    )

    existing = list(
        db.scalars(
            select(ComplianceAlert).where(
                ComplianceAlert.notice_id == notice_id
            )
        ).all()
    )
    alerted_match_ids = {a.match_id for a in existing if a.match_id is not None}

    new_alerts: list[ComplianceAlert] = []
    for match in matches:
        if match.id in alerted_match_ids:
            continue
        alerted_match_ids.add(match.id)
        severity, recommended_action = _ALERT_POLICY[match.match_strategy]
        new_alerts.append(
            ComplianceAlert(
                notice_id=notice_id,
                product_id=match.product_id,
                match_id=match.id,
                severity=severity,
                status=ComplianceAlertStatus.open,
                recommended_action=recommended_action,
            )
        )

    if new_alerts:
        db.add_all(new_alerts)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Compliance alert violates database constraints.",
            ) from exc
        for alert in new_alerts:
            db.refresh(alert)

    return [
        ComplianceAlertRead.model_validate(a)
        for a in (*existing, *new_alerts)
    ]


def _get_alert(db: Session, alert_id: UUID) -> ComplianceAlert:
    alert = db.get(ComplianceAlert, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compliance alert not found.",
        )
    return alert


def _require_actor(db: Session, actor_user_id: UUID | None) -> User:
    if actor_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="actor_user_id is required.",
        )
    actor = db.get(User, actor_user_id)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor user not found.",
        )
    return actor


def _assert_alert_transition(
    alert: ComplianceAlert,
    *,
    allowed_from: tuple[ComplianceAlertStatus, ...],
    verb: str,
) -> None:
    if alert.status not in allowed_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot {verb} a compliance alert in status "
                f"'{alert.status.value}'."
            ),
        )


def _alert_snapshot(alert: ComplianceAlert) -> dict[str, Any]:
    """JSON-safe before/after snapshot of the human-reviewable alert fields."""
    return {
        "status": alert.status.value,
        "recommended_action": alert.recommended_action.value,
        "resolved_by_user_id": (
            str(alert.resolved_by_user_id)
            if alert.resolved_by_user_id is not None
            else None
        ),
        "resolved_at": (
            alert.resolved_at.isoformat()
            if alert.resolved_at is not None
            else None
        ),
        "resolution_note": alert.resolution_note,
    }


def _build_decision_audit(
    alert: ComplianceAlert,
    *,
    actor_user_id: UUID,
    action: RegulatoryDecisionAction,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str,
    resolution_action: str,
) -> RegulatoryDecisionAuditLog:
    """Construct (but do not commit) the append-only decision audit row.

    Lives in `regulatory_decision_audit_logs` — never `operational_audit_logs`.
    """
    return RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=alert.notice_id,
        product_id=alert.product_id,
        actor_user_id=actor_user_id,
        action=action.value,
        before=before,
        after=after,
        event_metadata={
            "notice_id": str(alert.notice_id),
            "match_id": (
                str(alert.match_id) if alert.match_id is not None else None
            ),
            "product_id": (
                str(alert.product_id)
                if alert.product_id is not None
                else None
            ),
            "recommended_action": alert.recommended_action.value,
            "resolution_action": resolution_action,
        },
        reason=reason,
    )


def acknowledge_compliance_alert(
    db: Session,
    alert_id: UUID,
    payload: ComplianceAlertActionRequest,
    *,
    actor_user_id: UUID,
) -> ComplianceAlertRead:
    """Mark an open alert as acknowledged (seen, not yet resolved).

    `status` → `acknowledged`; the `resolved_*` fields stay NULL. Writes a
    `regulatory_decision_audit_logs` row. Never mutates the product and never
    calls `set_product_compliance()`.
    """
    actor = _require_actor(db, actor_user_id)
    alert = _get_alert(db, alert_id)
    _assert_alert_transition(
        alert, allowed_from=(ComplianceAlertStatus.open,), verb="acknowledge"
    )

    before = _alert_snapshot(alert)
    alert.status = ComplianceAlertStatus.acknowledged
    after = _alert_snapshot(alert)

    db.add(
        _build_decision_audit(
            alert,
            actor_user_id=actor.id,
            action=RegulatoryDecisionAction.alert_acknowledged,
            before=before,
            after=after,
            reason=payload.reason,
            resolution_action="acknowledge",
        )
    )
    _commit_or_422(db, "Compliance alert acknowledgement")
    db.refresh(alert)
    return ComplianceAlertRead.model_validate(alert)


def dismiss_compliance_alert(
    db: Session,
    alert_id: UUID,
    payload: ComplianceAlertActionRequest,
    *,
    actor_user_id: UUID,
) -> ComplianceAlertRead:
    """Dismiss an alert as not actionable.

    `status` → `dismissed`; sets `resolved_by_user_id`, `resolved_at` and
    stores `resolution_note`. Writes a `regulatory_decision_audit_logs` row.
    Never mutates the product and never calls `set_product_compliance()`.
    """
    actor = _require_actor(db, actor_user_id)
    alert = _get_alert(db, alert_id)
    _assert_alert_transition(
        alert,
        allowed_from=(
            ComplianceAlertStatus.open,
            ComplianceAlertStatus.acknowledged,
        ),
        verb="dismiss",
    )

    before = _alert_snapshot(alert)
    alert.status = ComplianceAlertStatus.dismissed
    alert.resolved_by_user_id = actor.id
    alert.resolved_at = datetime.now(UTC)
    alert.resolution_note = payload.reason
    after = _alert_snapshot(alert)

    db.add(
        _build_decision_audit(
            alert,
            actor_user_id=actor.id,
            action=RegulatoryDecisionAction.alert_dismissed,
            before=before,
            after=after,
            reason=payload.reason,
            resolution_action="dismiss",
        )
    )
    _commit_or_422(db, "Compliance alert dismissal")
    db.refresh(alert)
    return ComplianceAlertRead.model_validate(alert)


def resolve_compliance_alert(
    db: Session,
    alert_id: UUID,
    payload: ComplianceAlertResolveRequest,
    *,
    actor_user_id: UUID,
) -> ComplianceAlertRead:
    """Resolve an alert with an explicit admin action.

    `status` → `actioned`; sets `resolved_by_user_id`, `resolved_at` and stores
    `resolution_note`. Writes a `regulatory_decision_audit_logs` row whose
    action reflects the resolution:
      - `no_action` → `alert_resolved_no_action` (no product change);
      - `hold`      → `alert_resolved_hold` (delegates to
        `set_product_compliance()` → restricted + not allowed_for_sale);
      - `ban`       → `alert_resolved_ban` (delegates to
        `set_product_compliance()` → banned + not allowed_for_sale, which also
        cascades the existing inventory quarantine).

    For hold/ban the alert mutation and the decision-audit row are staged in
    the SAME session and committed atomically by `set_product_compliance()`'s
    single commit, so the alert close, the regulatory decision audit, the
    product compliance change and its `product_compliance_audit_logs` row all
    land together (or roll back together). The product is NEVER written
    directly here.
    """
    actor = _require_actor(db, actor_user_id)
    alert = _get_alert(db, alert_id)
    _assert_alert_transition(
        alert,
        allowed_from=(
            ComplianceAlertStatus.open,
            ComplianceAlertStatus.acknowledged,
        ),
        verb="resolve",
    )

    action = payload.action
    applies_compliance = action in (
        ComplianceAlertResolutionAction.hold,
        ComplianceAlertResolutionAction.ban,
    )
    if applies_compliance and alert.product_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot apply a '{action.value}' resolution to an alert with "
                "no associated product."
            ),
        )

    decision_action = {
        ComplianceAlertResolutionAction.no_action: (
            RegulatoryDecisionAction.alert_resolved_no_action
        ),
        ComplianceAlertResolutionAction.hold: (
            RegulatoryDecisionAction.alert_resolved_hold
        ),
        ComplianceAlertResolutionAction.ban: (
            RegulatoryDecisionAction.alert_resolved_ban
        ),
    }[action]

    before = _alert_snapshot(alert)
    alert.status = ComplianceAlertStatus.actioned
    alert.resolved_by_user_id = actor.id
    alert.resolved_at = datetime.now(UTC)
    alert.resolution_note = payload.resolution_note
    after = _alert_snapshot(alert)

    db.add(
        _build_decision_audit(
            alert,
            actor_user_id=actor.id,
            action=decision_action,
            before=before,
            after=after,
            reason=payload.resolution_note,
            resolution_action=action.value,
        )
    )

    if applies_compliance:
        # Real compliance change goes ONLY through set_product_compliance().
        # Its single commit atomically persists everything staged above
        # (alert close + decision audit) together with the product change,
        # the product_compliance_audit_logs row and — for ban — the inventory
        # quarantine cascade.
        if action == ComplianceAlertResolutionAction.hold:
            compliance_status = ComplianceStatus.restricted
        else:  # ban
            compliance_status = ComplianceStatus.banned
        reason = (
            f"Regulatory {action.value} via compliance alert {alert.id} "
            f"(notice {alert.notice_id}). {payload.resolution_note}"
        )
        try:
            set_product_compliance(
                db,
                alert.product_id,
                ProductComplianceUpdate(
                    compliance_status=compliance_status,
                    allowed_for_sale=False,
                    reason=reason,
                ),
                actor=actor,
            )
        except HTTPException:
            # set_product_compliance already rolled back on its own failure.
            db.rollback()
            raise
    else:
        _commit_or_422(db, "Compliance alert resolution")

    db.refresh(alert)
    return ComplianceAlertRead.model_validate(alert)


def _commit_or_422(db: Session, what: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{what} violates database constraints.",
        ) from exc


# --------------------------------------------------------------------- #
# Read-only listing/get helpers backing the admin API (F2.26.5.E)
# --------------------------------------------------------------------- #
#
# Pure queries — no mutation, no matching/alert side effects. They exist only
# so the route layer has paginated list + detail reads to delegate to.


def list_regulatory_notices(
    db: Session,
    *,
    limit: int = 25,
    offset: int = 0,
    source_id: UUID | None = None,
    notice_type: RegulatoryNoticeType | None = None,
) -> RegulatoryNoticeListResponse:
    """Paginated list of regulatory notices, newest first.

    Optional `source_id` / `notice_type` filters. `total` is computed before
    pagination. Read-only — never ingests, matches or alerts.
    """
    _assert_list_pagination(limit, offset)

    stmt = select(RegulatoryNotice)
    count_stmt = select(func.count()).select_from(RegulatoryNotice)

    if source_id is not None:
        stmt = stmt.where(RegulatoryNotice.source_id == source_id)
        count_stmt = count_stmt.where(
            RegulatoryNotice.source_id == source_id
        )
    if notice_type is not None:
        stmt = stmt.where(RegulatoryNotice.notice_type == notice_type)
        count_stmt = count_stmt.where(
            RegulatoryNotice.notice_type == notice_type
        )

    stmt = stmt.order_by(
        RegulatoryNotice.created_at.desc(), RegulatoryNotice.id.asc()
    ).limit(limit).offset(offset)

    rows = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0

    return RegulatoryNoticeListResponse(
        items=[RegulatoryNoticeRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def list_compliance_alerts(
    db: Session,
    *,
    limit: int = 25,
    offset: int = 0,
    status_filter: ComplianceAlertStatus | None = None,
    severity: ComplianceAlertSeverity | None = None,
    recommended_action: ComplianceRecommendedAction | None = None,
    product_id: UUID | None = None,
    notice_id: UUID | None = None,
) -> ComplianceAlertListResponse:
    """Paginated list of compliance alerts, newest first.

    Optional `status`, `severity`, `recommended_action`, `product_id` and
    `notice_id` filters. `total` is computed before pagination. Read-only.
    """
    _assert_list_pagination(limit, offset)

    stmt = select(ComplianceAlert)
    count_stmt = select(func.count()).select_from(ComplianceAlert)

    filters = []
    if status_filter is not None:
        filters.append(ComplianceAlert.status == status_filter)
    if severity is not None:
        filters.append(ComplianceAlert.severity == severity)
    if recommended_action is not None:
        filters.append(
            ComplianceAlert.recommended_action == recommended_action
        )
    if product_id is not None:
        filters.append(ComplianceAlert.product_id == product_id)
    if notice_id is not None:
        filters.append(ComplianceAlert.notice_id == notice_id)
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    stmt = stmt.order_by(
        ComplianceAlert.created_at.desc(), ComplianceAlert.id.asc()
    ).limit(limit).offset(offset)

    rows = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0

    return ComplianceAlertListResponse(
        items=[ComplianceAlertRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_compliance_alert(
    db: Session, alert_id: UUID
) -> ComplianceAlertRead:
    """Fetch a single compliance alert (404 if missing)."""
    return ComplianceAlertRead.model_validate(_get_alert(db, alert_id))


def list_regulatory_decisions_for_alert(
    db: Session,
    alert_id: UUID,
    *,
    limit: int = 25,
    offset: int = 0,
) -> RegulatoryDecisionAuditLogListResponse:
    """Paginated decision trail for one compliance alert, newest first.

    Reads append-only `regulatory_decision_audit_logs` scoped to `alert_id`.
    Raises 404 (via `_get_alert`) if the alert does not exist. `total` is the
    decision count for the alert, computed before pagination. Strictly
    read-only: never mutates the alert, product, inventory, or any audit row.
    """
    _assert_list_pagination(limit, offset)

    # 404 if the alert is missing, matching the other alert-scoped helpers.
    _get_alert(db, alert_id)

    stmt = (
        select(RegulatoryDecisionAuditLog)
        .where(RegulatoryDecisionAuditLog.alert_id == alert_id)
        .order_by(
            RegulatoryDecisionAuditLog.created_at.desc(),
            RegulatoryDecisionAuditLog.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    count_stmt = (
        select(func.count())
        .select_from(RegulatoryDecisionAuditLog)
        .where(RegulatoryDecisionAuditLog.alert_id == alert_id)
    )

    rows = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0

    return RegulatoryDecisionAuditLogListResponse(
        items=[RegulatoryDecisionAuditLogRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
