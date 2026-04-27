"""Service layer for products, variants and compliance.

All business logic for the catalog lives here. Routers in
`app.api.routes` should call these functions and translate the
HTTPExceptions raised here straight back to the client. The rules
encoded in this module match `app.domain.products_rules`.

Conventions:
- Each function takes a Session as its first argument and is
  responsible for its own commit/rollback. Routers do not need to
  catch IntegrityError — this layer translates them to HTTP errors.
- Read functions raise HTTPException(404) when a resource is missing
  so routers can `raise` directly without extra checks.
- `set_product_compliance` is the only path that mutates compliance
  fields, and it always writes an audit log row in the same
  transaction.
"""

from datetime import UTC
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import User
from app.schemas.products import ProductComplianceUpdate
from app.schemas.products import ProductCreate
from app.schemas.products import ProductUpdate
from app.schemas.products import VariantCreate
from app.schemas.products import VariantUpdate


# --------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------- #


def _variant_unique_violation(exc: IntegrityError) -> HTTPException:
    """Translate a UNIQUE constraint violation on product_variants into a
    409 with a specific detail.

    Rejects on `uq_product_variants_sku` map to "SKU already exists.".
    Rejects on the auto-named barcode unique index map to "Barcode
    already exists.". Any other variant unique violation falls back to a
    generic 409 so we never leak the raw psycopg message.
    """
    message = str(exc.orig) if exc.orig is not None else str(exc)
    lowered = message.lower()
    if "uq_product_variants_sku" in lowered or "(sku)" in lowered:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU already exists.",
        )
    if "barcode" in lowered:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Barcode already exists.",
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Variant conflicts with existing data.",
    )


# --------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------- #


def create_product(db: Session, payload: ProductCreate) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # The schema's banned-implies-not-allowed validator should have
        # caught the contradictory state already; this branch covers
        # other DB-level violations (e.g. CHECK reason_non_empty on
        # adjacent inserts) so we never bubble raw SQL errors.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product violates database constraints.",
        ) from exc
    db.refresh(product)
    return product


def get_product(db: Session, product_id: UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    return product


def list_products(
    db: Session,
    *,
    only_active: bool = False,
    only_sellable: bool = False,
    compliance_status: ComplianceStatus | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Product]:
    """List products. `only_sellable` filters with the canonical rule
    so callers don't have to combine three boolean flags themselves.
    """
    stmt = select(Product)
    if only_active:
        stmt = stmt.where(Product.is_active.is_(True))
    if only_sellable:
        stmt = stmt.where(
            Product.is_active.is_(True),
            Product.allowed_for_sale.is_(True),
            Product.compliance_status == ComplianceStatus.allowed,
        )
    if compliance_status is not None:
        stmt = stmt.where(Product.compliance_status == compliance_status)
    if category is not None:
        stmt = stmt.where(Product.category == category)
    stmt = stmt.order_by(Product.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def update_product(
    db: Session,
    product_id: UUID,
    payload: ProductUpdate,
) -> Product:
    """Partial update for non-compliance fields.

    Compliance must go through set_product_compliance so the audit log
    is written. ProductUpdate schema does not expose those fields so a
    well-behaved caller cannot bypass the rule.
    """
    product = get_product(db, product_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(product, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product update violates database constraints.",
        ) from exc
    db.refresh(product)
    return product


def delete_or_deactivate_product(
    db: Session,
    product_id: UUID,
    *,
    hard: bool = False,
) -> Product | None:
    """Soft-delete by default (is_active=False). hard=True drops the row.

    Hard delete CASCADEs to variants AND compliance audit logs, which
    erases the regulatory trail. Prefer the soft path unless the caller
    has a documented reason to wipe history.
    """
    product = get_product(db, product_id)
    if hard:
        db.delete(product)
        db.commit()
        return None
    product.is_active = False
    db.commit()
    db.refresh(product)
    return product


# --------------------------------------------------------------------- #
# Variants
# --------------------------------------------------------------------- #


def create_variant(db: Session, payload: VariantCreate) -> ProductVariant:
    # 404 the missing product instead of letting the FK surface as 409.
    get_product(db, payload.product_id)

    variant = ProductVariant(**payload.model_dump())
    db.add(variant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _variant_unique_violation(exc) from exc
    db.refresh(variant)
    return variant


def get_variant(db: Session, variant_id: UUID) -> ProductVariant:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant not found.",
        )
    return variant


def list_variants_for_product(
    db: Session,
    product_id: UUID,
    *,
    only_active: bool = False,
) -> list[ProductVariant]:
    # 404 if the parent product is missing — keeps responses consistent
    # with /products/{id}/variants endpoints later.
    get_product(db, product_id)
    stmt = select(ProductVariant).where(
        ProductVariant.product_id == product_id
    )
    if only_active:
        stmt = stmt.where(ProductVariant.is_active.is_(True))
    return list(db.scalars(stmt.order_by(ProductVariant.created_at.asc())).all())


def update_variant(
    db: Session,
    variant_id: UUID,
    payload: VariantUpdate,
) -> ProductVariant:
    variant = get_variant(db, variant_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(variant, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _variant_unique_violation(exc) from exc
    db.refresh(variant)
    return variant


def delete_or_deactivate_variant(
    db: Session,
    variant_id: UUID,
    *,
    hard: bool = False,
) -> ProductVariant | None:
    """Soft-delete by default (is_active=False). hard=True drops the row
    and CASCADEs to inventory_items and inventory_logs."""
    variant = get_variant(db, variant_id)
    if hard:
        db.delete(variant)
        db.commit()
        return None
    variant.is_active = False
    db.commit()
    db.refresh(variant)
    return variant


# --------------------------------------------------------------------- #
# Compliance
# --------------------------------------------------------------------- #


def assert_product_sellable(product: Product) -> None:
    """Enforce the canonical sellability rule from products_rules §3.

    Raises HTTPException(422) listing the failing flags so the caller
    knows exactly why a sale path is blocked.
    """
    reasons: list[str] = []
    if product.compliance_status != ComplianceStatus.allowed:
        reasons.append(
            f"compliance_status is '{product.compliance_status.value}'"
        )
    if not product.allowed_for_sale:
        reasons.append("allowed_for_sale is false")
    if not product.is_active:
        reasons.append("is_active is false")

    if reasons:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product is not sellable: " + ", ".join(reasons) + ".",
        )


def write_compliance_audit_log(
    db: Session,
    *,
    product: Product,
    previous_compliance_status: ComplianceStatus,
    new_compliance_status: ComplianceStatus,
    previous_allowed_for_sale: bool,
    new_allowed_for_sale: bool,
    reason: str,
    changed_by_user: User | None,
) -> ProductComplianceAuditLog:
    """Append an audit row to the session.

    Does NOT commit. The caller (set_product_compliance) commits in a
    single transaction together with the product mutation so the two
    rows always land or roll back together.
    """
    audit = ProductComplianceAuditLog(
        product_id=product.id,
        previous_compliance_status=previous_compliance_status,
        new_compliance_status=new_compliance_status,
        previous_allowed_for_sale=previous_allowed_for_sale,
        new_allowed_for_sale=new_allowed_for_sale,
        reason=reason,
        changed_by_user_id=(
            changed_by_user.id if changed_by_user is not None else None
        ),
    )
    db.add(audit)
    return audit


def set_product_compliance(
    db: Session,
    product_id: UUID,
    payload: ProductComplianceUpdate,
    *,
    actor: User | None,
) -> Product:
    """Atomically change a product's compliance state and write the
    audit log entry.

    1. Load the product (404 if missing).
    2. Snapshot previous compliance_status and allowed_for_sale.
    3. Mutate the product (status, allowed_for_sale, last_compliance_check).
    4. Insert a ProductComplianceAuditLog row in the same session.
    5. Commit once. If any step fails (including the DB CHECK
       ck_products_banned_implies_not_allowed_for_sale), the transaction
       rolls back so neither the product change nor the audit row land.

    The audit log records every successful invocation, even when the
    status did not change — that is the regulatory contract: every
    review is recorded, not just transitions.
    """
    product = get_product(db, product_id)

    previous_compliance_status = product.compliance_status
    previous_allowed_for_sale = product.allowed_for_sale

    product.compliance_status = payload.compliance_status
    product.allowed_for_sale = payload.allowed_for_sale
    product.last_compliance_check = datetime.now(UTC)

    write_compliance_audit_log(
        db,
        product=product,
        previous_compliance_status=previous_compliance_status,
        new_compliance_status=payload.compliance_status,
        previous_allowed_for_sale=previous_allowed_for_sale,
        new_allowed_for_sale=payload.allowed_for_sale,
        reason=payload.reason,
        changed_by_user=actor,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Compliance change violates database constraints.",
        ) from exc
    db.refresh(product)
    return product
