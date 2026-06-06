"""Service tests for the regulatory product matching engine (F2.26.5.C).

Exercises `app.services.regulatory.detect_regulatory_product_matches` and the
`normalize_match_value` helper against the real (migrated) Postgres test
database via the transactional `db_session`:
  - matching per strategy (name/brand/category/sku/barcode/flavor);
  - no-match, multiple payload products, duplicate-value + idempotent dedupe;
  - product-level (`variant_id is None`) service dedupe;
  - confidence ranges and matched_fields provenance;
  - normalization (case/whitespace insensitivity, no false matches);
  - side-effect safety (no product/inventory/alert/audit mutation) + a static
    import guard.

Style mirrors tests/test_regulatory_ingestion.py.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceStatus
from app.db.models import OperationalAuditLog
from app.db.models import Product
from app.db.models import ProductApprovalStatus
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryMatchStrategy
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryProductMatch
from app.schemas.regulatory import RegulatoryNoticeIngestRequest
from app.schemas.regulatory import RegulatorySourceCreate
from app.services import regulatory as svc


# --------------------------------------------------------------------- #
# Helpers / fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        *,
        name: str = "Example Vape",
        brand: str | None = "Example Brand",
        category: str = "ENDS",
    ) -> Product:
        product = Product(
            name=name,
            brand=brand,
            category=category,
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
            is_active=True,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


@pytest.fixture
def make_variant(db_session: Session) -> Callable[..., ProductVariant]:
    def _create(
        product: Product,
        *,
        sku: str | None = None,
        barcode: str | None = None,
        flavor: str | None = None,
    ) -> ProductVariant:
        variant = ProductVariant(
            product_id=product.id,
            sku=sku or f"sku-{uuid.uuid4().hex[:8]}",
            barcode=barcode,
            flavor=flavor,
            price=Decimal("9.99"),
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_notice(db_session: Session) -> Callable[..., RegulatoryNotice]:
    def _create(payload: dict) -> RegulatoryNotice:
        source = svc.create_regulatory_source(
            db_session,
            RegulatorySourceCreate.model_validate(
                {"name": f"S {uuid.uuid4().hex[:8]}", "kind": "manual"}
            ),
        )
        read = svc.ingest_regulatory_notice(
            db_session,
            RegulatoryNoticeIngestRequest.model_validate(
                {
                    "source_id": source.id,
                    "title": "t",
                    "notice_type": "manual_snapshot",
                    "payload": payload,
                }
            ),
        )
        return db_session.get(RegulatoryNotice, read.id)

    return _create


# ===================================================================== #
# 1. Matching per strategy
# ===================================================================== #


def test_match_by_product_name(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="Example Vape")
    notice = make_notice({"product_name": "Example Vape"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    m = matches[0]
    assert m.product_id == product.id
    assert m.variant_id is None
    assert m.match_strategy is RegulatoryMatchStrategy.name
    assert m.confidence == Decimal("0.90")


def test_match_by_brand(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="A", brand="Example Brand", category="x")
    notice = make_notice({"brand": "Example Brand"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    assert matches[0].match_strategy is RegulatoryMatchStrategy.brand
    assert matches[0].confidence == Decimal("0.70")
    assert matches[0].product_id == product.id


def test_match_by_category(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="A", brand=None, category="ENDS")
    notice = make_notice({"category": "ENDS"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    assert matches[0].match_strategy is RegulatoryMatchStrategy.category
    assert matches[0].confidence == Decimal("0.50")
    assert matches[0].product_id == product.id


def test_match_by_variant_sku(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="No Name Match", brand=None, category="zzz")
    variant = make_variant(product, sku="SKU-123")
    notice = make_notice({"sku": "SKU-123"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    m = matches[0]
    assert m.match_strategy is RegulatoryMatchStrategy.sku
    assert m.confidence == Decimal("0.95")
    assert m.product_id == product.id
    assert m.variant_id == variant.id


def test_match_by_variant_barcode(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="No Name", brand=None, category="zzz")
    variant = make_variant(product, barcode="012345678905")
    notice = make_notice({"barcode": "012345678905"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    assert matches[0].match_strategy is RegulatoryMatchStrategy.barcode
    assert matches[0].confidence == Decimal("1.00")
    assert matches[0].variant_id == variant.id


def test_match_by_variant_flavor(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="No Name", brand=None, category="zzz")
    variant = make_variant(product, flavor="Mint")
    notice = make_notice({"flavor": "Mint"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    assert matches[0].match_strategy is RegulatoryMatchStrategy.flavor
    assert matches[0].confidence == Decimal("0.60")
    assert matches[0].variant_id == variant.id


def test_no_match_returns_empty(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    make_product(name="Totally Different", brand="Other", category="other")
    notice = make_notice({"product_name": "Nonexistent Product"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert matches == []
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryProductMatch)
    ) == 0


def test_multiple_payload_products(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    p1 = make_product(name="Alpha Vape", brand=None, category="c1")
    p2 = make_product(name="Beta Vape", brand=None, category="c2")
    notice = make_notice(
        {
            "products": [
                {"product_name": "Alpha Vape"},
                {"product_name": "Beta Vape"},
            ]
        }
    )
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    matched_ids = {m.product_id for m in matches}
    assert matched_ids == {p1.id, p2.id}
    # payload_path provenance reflects the list index.
    paths = {m.matched_fields["payload_path"] for m in matches}
    assert paths == {"products[0].product_name", "products[1].product_name"}


def test_multiple_strategies_same_product_distinct_rows(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="Example Vape", brand="Example Brand", category="ENDS")
    notice = make_notice(
        {
            "product_name": "Example Vape",
            "brand": "Example Brand",
            "category": "ENDS",
        }
    )
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    strategies = {m.match_strategy for m in matches}
    assert strategies == {
        RegulatoryMatchStrategy.name,
        RegulatoryMatchStrategy.brand,
        RegulatoryMatchStrategy.category,
    }
    assert all(m.product_id == product.id for m in matches)


# ===================================================================== #
# 2. Dedupe + idempotency
# ===================================================================== #


def test_duplicate_payload_values_no_duplicate_rows(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    make_product(name="Example Vape", brand=None, category="c")
    notice = make_notice(
        {
            "products": [
                {"product_name": "Example Vape"},
                {"product_name": "Example Vape"},  # duplicate
            ]
        }
    )
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryProductMatch)
    ) == 1


def test_detection_is_idempotent(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    make_product(name="Example Vape", brand=None, category="c")
    notice = make_notice({"product_name": "Example Vape"})

    first = svc.detect_regulatory_product_matches(db_session, notice.id)
    second = svc.detect_regulatory_product_matches(db_session, notice.id)

    assert len(first) == 1
    assert len(second) == 1
    assert {m.id for m in first} == {m.id for m in second}
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryProductMatch)
    ) == 1


def test_product_level_null_variant_dedupes_at_service_level(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    # Two detection runs on a product-level (variant_id IS NULL) match must
    # NOT create a second row, even though the Postgres unique index treats
    # NULL variant_ids as distinct. The service-level dedupe is the guard.
    make_product(name="Example Vape", brand=None, category="c")
    notice = make_notice({"product_name": "Example Vape"})

    svc.detect_regulatory_product_matches(db_session, notice.id)
    svc.detect_regulatory_product_matches(db_session, notice.id)

    rows = list(
        db_session.scalars(
            select(RegulatoryProductMatch).where(
                RegulatoryProductMatch.notice_id == notice.id
            )
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].variant_id is None


# ===================================================================== #
# 3. Confidence + matched_fields provenance
# ===================================================================== #


def test_confidence_values_within_db_range(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="Example Vape", brand="Example Brand", category="ENDS")
    make_variant(product, sku="SKU-1", barcode="012345678905", flavor="Mint")
    notice = make_notice(
        {
            "product_name": "Example Vape",
            "brand": "Example Brand",
            "category": "ENDS",
            "sku": "SKU-1",
            "barcode": "012345678905",
            "flavor": "Mint",
        }
    )
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 6
    for m in matches:
        assert Decimal("0") <= m.confidence <= Decimal("1")


def test_matched_fields_provenance(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="No Name", brand=None, category="zzz")
    make_variant(product, sku="SKU-123")
    notice = make_notice({"products": [{"sku": "SKU-123"}]})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    mf = matches[0].matched_fields
    assert mf["strategy"] == "sku"
    assert mf["notice_value"] == "SKU-123"
    assert mf["catalog_value"] == "SKU-123"
    assert mf["payload_path"] == "products[0].sku"


# ===================================================================== #
# 4. Normalization
# ===================================================================== #


def test_normalize_helper_behavior():
    n = svc.normalize_match_value
    assert n("  Example   Vape  ") == n("example vape")
    assert n("MINT") == n("mint")
    assert n(None) is None
    assert n("   ") is None
    assert n("Example Vape") != n("Other Vape")


def test_match_is_case_and_whitespace_insensitive(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="Example   Vape", brand=None, category="c")
    notice = make_notice({"product_name": "  example vape  "})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    assert matches[0].product_id == product.id


def test_no_false_match_for_unrelated_value(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    make_product(name="Example Vape", brand=None, category="c")
    notice = make_notice({"product_name": "Examplee Vape"})  # typo, no match
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert matches == []


def test_missing_field_skips_strategy(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    # Payload has only brand; name/category strategies are skipped.
    product = make_product(name="Example Vape", brand="Example Brand", category="ENDS")
    notice = make_notice({"brand": "Example Brand"})
    matches = svc.detect_regulatory_product_matches(db_session, notice.id)
    assert len(matches) == 1
    assert matches[0].match_strategy is RegulatoryMatchStrategy.brand
    assert matches[0].product_id == product.id


def test_invalid_notice_raises_404(db_session: Session):
    with pytest.raises(HTTPException) as exc:
        svc.detect_regulatory_product_matches(db_session, uuid.uuid4())
    assert exc.value.status_code == 404


# ===================================================================== #
# 5. Side-effect safety
# ===================================================================== #


def test_matching_has_no_side_effects(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="Example Vape", brand="Example Brand", category="ENDS")
    variant = make_variant(product, sku="SKU-1", barcode="012345678905", flavor="Mint")

    before = (
        product.compliance_status,
        product.allowed_for_sale,
        product.approval_status,
    )
    variant_before = (variant.sku, variant.barcode, variant.flavor)

    notice = make_notice(
        {
            "product_name": "Example Vape",
            "brand": "Example Brand",
            "category": "ENDS",
            "sku": "SKU-1",
            "barcode": "012345678905",
            "flavor": "Mint",
        }
    )
    svc.detect_regulatory_product_matches(db_session, notice.id)

    db_session.refresh(product)
    db_session.refresh(variant)
    # Product compliance / sellability / approval untouched.
    assert (
        product.compliance_status,
        product.allowed_for_sale,
        product.approval_status,
    ) == before
    assert product.compliance_status == ComplianceStatus.allowed
    assert product.approval_status == ProductApprovalStatus.approved
    # Variant fields untouched.
    assert (variant.sku, variant.barcode, variant.flavor) == variant_before

    # No alerts, decision audits, or operational audits created.
    assert db_session.scalar(
        select(func.count()).select_from(ComplianceAlert)
    ) == 0
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryDecisionAuditLog)
    ) == 0
    assert db_session.scalar(
        select(func.count())
        .select_from(OperationalAuditLog)
        .where(OperationalAuditLog.target_id.in_([product.id, variant.id]))
    ) == 0


def test_matching_module_imports_no_forbidden_machinery():
    # The regulatory module legitimately imports ComplianceAlert /
    # RegulatoryDecisionAuditLog / set_product_compliance (F2.26.5.D — alerts
    # + resolution). The ENDURING file-level invariants are: never write
    # operational audit, never touch Inventory models directly (the ban
    # cascade is owned by set_product_compliance), and never import
    # notification/email.
    import ast

    import app.services.regulatory as mod

    with open(mod.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    imported: list[str] = []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
            names.extend(alias.name for alias in node.names)

    forbidden_names = {
        "write_operational_audit_log",
        "OperationalAuditLog",
        "InventoryItem",
        "InventoryLog",
        "InventoryStatus",
    }
    leaked = forbidden_names & set(names)
    assert not leaked, f"unexpected import: {leaked}"
    assert "app.services.operational_audit" not in imported
    assert not any("notification" in m or "email" in m for m in imported)
