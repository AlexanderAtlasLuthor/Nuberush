from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.deps import require_admin
from app.api.deps import require_manager_or_above
from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductApprovalStatus
from app.db.models import ProductComplianceAuditLog
from app.db.models import User
from app.db.session import get_db
from app.schemas.products import ProductComplianceAuditLogRead
from app.schemas.products import ProductComplianceUpdate
from app.schemas.products import ProductCreate
from app.schemas.products import ProductImageConfirmRequest
from app.schemas.products import ProductImageRead
from app.schemas.products import ProductImageUploadUrlRequest
from app.schemas.products import ProductImageUploadUrlResponse
from app.schemas.products import ProductRead
from app.schemas.products import ProductReject
from app.schemas.products import ProductUpdate
from app.schemas.products import VariantCreate
from app.schemas.products import VariantRead
from app.schemas.products import VariantUpdate
from app.services import products as svc
from app.services import storage as storage_svc
from app.services.storage import SupabaseStorageError


router = APIRouter(prefix="/products", tags=["products"])


# --------------------------------------------------------------------- #
# Reads — any authenticated user
# --------------------------------------------------------------------- #


@router.get("", response_model=list[ProductRead])
def list_products(
    only_active: bool = Query(default=False),
    only_sellable: bool = Query(default=False),
    only_blocked: bool = Query(default=False),
    compliance_status: ComplianceStatus | None = Query(default=None),
    approval_status: ProductApprovalStatus | None = Query(default=None),
    category: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Product]:
    return svc.list_products(
        db,
        actor=current_user,
        only_active=only_active,
        only_sellable=only_sellable,
        only_blocked=only_blocked,
        compliance_status=compliance_status,
        approval_status=approval_status,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Product:
    return svc.get_product(db, product_id)


@router.get(
    "/{product_id}/variants",
    response_model=list[VariantRead],
)
def list_variants(
    product_id: UUID,
    only_active: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_variants_for_product(
        db, product_id, only_active=only_active
    )


@router.get("/{product_id}/sellable")
def check_product_sellable(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Returns 200 with {sellable: true} if the product is sellable.

    Returns 422 with the failing flags if it is not. Built on top of
    services.products.assert_product_sellable so the rule cannot drift.
    """
    product = svc.get_product(db, product_id)
    svc.assert_product_sellable(product)
    return {"product_id": str(product.id), "sellable": True}


# --------------------------------------------------------------------- #
# Products — create open to manager-or-above; admin still owns the
# update / delete paths. The role split lives in services.products.create_product:
#   - admin     → row is approved on insert
#   - owner /   → row is pending; admin reviews via /approve or /reject
#     manager
# --------------------------------------------------------------------- #


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
) -> Product:
    return svc.create_product(db, payload, actor=current_user)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Product:
    return svc.update_product(db, product_id, payload)


@router.post(
    "/{product_id}/approve",
    response_model=ProductRead,
)
def approve_product(
    product_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Product:
    return svc.approve_product(db, product_id, actor=current_user)


@router.post(
    "/{product_id}/reject",
    response_model=ProductRead,
)
def reject_product(
    product_id: UUID,
    payload: ProductReject,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Product:
    return svc.reject_product(db, product_id, payload, actor=current_user)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_product(
    product_id: UUID,
    hard: bool = Query(default=False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    svc.delete_or_deactivate_product(db, product_id, hard=hard)
    return None


# --------------------------------------------------------------------- #
# Variants — admin only
# --------------------------------------------------------------------- #


@router.post(
    "/{product_id}/variants",
    response_model=VariantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(
    product_id: UUID,
    payload: VariantCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if payload.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product_id in body does not match path.",
        )
    return svc.create_variant(db, payload)


# Variant detail/update/delete are at /variants/{variant_id} since a
# variant has its own globally-unique id and routing through the parent
# product would force callers to know the parent_id when they already
# have the variant id (e.g. from inventory or order flows).
variants_router = APIRouter(prefix="/variants", tags=["products"])


@variants_router.patch("/{variant_id}", response_model=VariantRead)
def update_variant(
    variant_id: UUID,
    payload: VariantUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return svc.update_variant(db, variant_id, payload)


@variants_router.delete(
    "/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_variant(
    variant_id: UUID,
    hard: bool = Query(default=False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    svc.delete_or_deactivate_variant(db, variant_id, hard=hard)
    return None


# --------------------------------------------------------------------- #
# Compliance — admin only
# --------------------------------------------------------------------- #


@router.patch(
    "/{product_id}/compliance", response_model=ProductRead
)
def set_product_compliance(
    product_id: UUID,
    payload: ProductComplianceUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Product:
    return svc.set_product_compliance(
        db, product_id, payload, actor=current_user
    )


# --------------------------------------------------------------------- #
# Product images — admin only (F2.22.4.F)
# --------------------------------------------------------------------- #


@router.post(
    "/{product_id}/image-upload-url",
    response_model=ProductImageUploadUrlResponse,
)
def create_product_image_upload_url(
    product_id: UUID,
    payload: ProductImageUploadUrlRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductImageUploadUrlResponse:
    """Issue a short-lived signed upload URL for a product image.

    Admin-only. The bucket is the locked `product-images` bucket; the
    object key is generated server-side under `products/{product_id}/`
    so the client cannot influence it. The signed URL itself is
    minted by Supabase Storage using the server-side service-role
    credentials — the frontend never sees that key.
    """
    try:
        return storage_svc.create_product_image_upload_url(
            db, product_id, payload
        )
    except SupabaseStorageError as exc:
        # Coarse 502 — the underlying Supabase failure stays in the
        # exception chain (server logs), not the response body. No
        # service-role key, URL, or request body is echoed.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream storage service unavailable.",
        ) from exc


@router.post(
    "/{product_id}/images",
    response_model=ProductImageRead,
    status_code=status.HTTP_201_CREATED,
)
def confirm_product_image(
    product_id: UUID,
    payload: ProductImageConfirmRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Confirm a completed upload and upsert the metadata row.

    Admin-only. The unique(product_id) constraint enforces one primary
    image per product, so re-confirming replaces the existing row in
    place rather than inserting a duplicate. The uploader on the
    metadata row is always the current admin.
    """
    return storage_svc.confirm_product_image(
        db, product_id, payload, actor=current_user
    )


@router.delete(
    "/{product_id}/images",
    response_model=ProductRead,
)
def delete_product_image(
    product_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Product:
    """Clear a product's primary image. Admin-only.

    Idempotent: clearing a product that has no image returns it
    unchanged (`primary_image: null`) with 200 rather than 404. The
    metadata row is removed and the storage object cleaned up in the
    same operation; if the storage cleanup fails the whole operation is
    rolled back and a controlled 502 is returned, keeping the metadata
    row and the storage object in sync.
    """
    try:
        return storage_svc.delete_product_image(db, product_id)
    except SupabaseStorageError as exc:
        # Coarse 502 — the underlying Supabase failure stays in the
        # exception chain (server logs), not the response body.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream storage service unavailable.",
        ) from exc


@router.get(
    "/{product_id}/compliance-audit",
    response_model=list[ProductComplianceAuditLogRead],
)
def list_product_compliance_audit(
    product_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # 404 if product missing — keeps response consistent with other
    # /products/{id}/* endpoints.
    svc.get_product(db, product_id)
    stmt = (
        select(ProductComplianceAuditLog)
        .where(ProductComplianceAuditLog.product_id == product_id)
        .order_by(ProductComplianceAuditLog.created_at.desc())
    )
    return list(db.scalars(stmt).all())
