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
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryStatus
from app.db.models import Product
from app.db.models import ProductApprovalStatus
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import User
from app.db.models import UserRole
from app.schemas.products import ProductComplianceUpdate
from app.schemas.products import ProductCreate
from app.schemas.products import ProductReject
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


def create_product(
    db: Session,
    payload: ProductCreate,
    *,
    actor: User,
) -> Product:
    """Create a product, branching on the actor's role.

    - Admin → goes straight into the catalog as `approved` with the
      actor recorded as the reviewer (so admin-curated rows aren't
      visually distinguishable from a proposal that the same admin
      approved).
    - Manager / owner → inserted as `pending` and tied to the actor's
      store via `proposed_by_*`. Compliance fields are forced to the
      conservative `allowed` / `allowed_for_sale=True` defaults
      because store users are not authoritative on compliance; the
      admin sets the final compliance state at approval time via
      the existing compliance flow.

    Callers other than admin/manager/owner are rejected by the route
    via `require_manager_or_above`; we still re-validate role here
    so service-level callers cannot bypass the rule.
    """
    fields = payload.model_dump()
    now = datetime.now(UTC)

    if actor.role == UserRole.admin:
        fields["approval_status"] = ProductApprovalStatus.approved
        fields["reviewed_by_user_id"] = actor.id
        fields["reviewed_at"] = now
    elif actor.role in (UserRole.owner, UserRole.manager):
        if actor.store_id is None:
            # Defensive: the data model says non-admin users have a
            # store_id. If that invariant is ever broken, surface it
            # as 422 instead of writing a half-formed proposal.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Store users must be bound to a store to propose "
                    "products."
                ),
            )
        fields["approval_status"] = ProductApprovalStatus.pending
        fields["proposed_by_store_id"] = actor.store_id
        fields["proposed_by_user_id"] = actor.id
        # Store-proposed rows always land with conservative compliance
        # defaults; admin is the source of truth on compliance and
        # decides the final state at approval time.
        fields["compliance_status"] = ComplianceStatus.allowed
        fields["allowed_for_sale"] = True
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to create products.",
        )

    product = Product(**fields)
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
    actor: User,
    only_active: bool = False,
    only_sellable: bool = False,
    compliance_status: ComplianceStatus | None = None,
    approval_status: ProductApprovalStatus | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Product]:
    """List products. `only_sellable` filters with the canonical rule
    so callers don't have to combine the booleans themselves.

    Approval-status visibility (server-enforced):

    - Admin sees every row. If `approval_status` is set, the filter
      applies as-is.
    - Non-admin sees `approved` rows AND their own store's `pending`
      proposals. Rejected rows are visible to the proposing store too
      (so they can see why) but not to other stores. The optional
      `approval_status` query narrows further within that visibility
      window; passing `approval_status=approved` from a store call is
      effectively a no-op since the union already includes them.
    """
    stmt = select(Product)
    if only_active:
        stmt = stmt.where(Product.is_active.is_(True))
    if only_sellable:
        # Mirror assert_product_sellable: only approved + compliant +
        # active + allowed rows are sellable.
        stmt = stmt.where(
            Product.is_active.is_(True),
            Product.allowed_for_sale.is_(True),
            Product.compliance_status == ComplianceStatus.allowed,
            Product.approval_status == ProductApprovalStatus.approved,
        )
    if compliance_status is not None:
        stmt = stmt.where(Product.compliance_status == compliance_status)
    if category is not None:
        stmt = stmt.where(Product.category == category)

    if actor.role == UserRole.admin:
        if approval_status is not None:
            stmt = stmt.where(Product.approval_status == approval_status)
    else:
        visibility = Product.approval_status == ProductApprovalStatus.approved
        if actor.store_id is not None:
            from sqlalchemy import or_

            visibility = or_(
                visibility,
                Product.proposed_by_store_id == actor.store_id,
            )
        stmt = stmt.where(visibility)
        if approval_status is not None:
            stmt = stmt.where(Product.approval_status == approval_status)

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

    A product must clear BOTH the compliance gate (compliance_status,
    allowed_for_sale, is_active) AND the approval gate
    (approval_status == approved) to sell.
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
    if product.approval_status != ProductApprovalStatus.approved:
        reasons.append(
            f"approval_status is '{product.approval_status.value}'"
        )

    if reasons:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product is not sellable: " + ", ".join(reasons) + ".",
        )


# --------------------------------------------------------------------- #
# Approval workflow (admin-only)
# --------------------------------------------------------------------- #


def approve_product(
    db: Session,
    product_id: UUID,
    *,
    actor: User,
) -> Product:
    """Mark a product as approved. Admin-only at the service layer.

    Idempotent on already-approved rows — re-approving a row simply
    refreshes the reviewer / timestamp. Approving a previously-rejected
    row clears the rejection_reason so the row obeys the
    `ck_products_rejected_iff_reason` constraint and so stale rejection
    text never lingers on a now-curated product.
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    product = get_product(db, product_id)
    product.approval_status = ProductApprovalStatus.approved
    product.reviewed_by_user_id = actor.id
    product.reviewed_at = datetime.now(UTC)
    product.rejection_reason = None
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Approval violates database constraints.",
        ) from exc
    db.refresh(product)
    return product


def reject_product(
    db: Session,
    product_id: UUID,
    payload: ProductReject,
    *,
    actor: User,
) -> Product:
    """Mark a product as rejected with a required reason. Admin-only."""
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    product = get_product(db, product_id)
    product.approval_status = ProductApprovalStatus.rejected
    product.reviewed_by_user_id = actor.id
    product.reviewed_at = datetime.now(UTC)
    product.rejection_reason = payload.reason
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection violates database constraints.",
        ) from exc
    db.refresh(product)
    return product


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

    # Compliance propagation (inventory_rules §6): banning a product
    # cascades to status=quarantined on every InventoryItem linked to
    # any of its variants, in the SAME transaction as the compliance
    # update and audit log row above. We deliberately do NOT write
    # InventoryLog rows here — this is a compliance event, not a
    # stock movement; the regulatory trail lives in the audit row
    # already added by write_compliance_audit_log.
    #
    # The reverse transition (banned -> allowed/restricted) does NOT
    # auto-lift quarantines: a manager must review and lift each
    # affected item via the inventory status endpoint.
    if payload.compliance_status == ComplianceStatus.banned:
        db.execute(
            update(InventoryItem)
            .where(
                InventoryItem.variant_id.in_(
                    select(ProductVariant.id).where(
                        ProductVariant.product_id == product_id
                    )
                ),
                InventoryItem.status != InventoryStatus.quarantined,
            )
            .values(status=InventoryStatus.quarantined)
            .execution_options(synchronize_session="fetch")
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
