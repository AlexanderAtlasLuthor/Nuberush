"""Server-side Supabase Storage integration for product images (F2.22.4.F).

FastAPI is the authority for permissions, validation, object-key shape and
metadata writes. This module is the thin server-side wrapper that:

  * Validates an admin's upload-URL request (filename, content type, size).
  * Generates the safe object key under the product prefix.
  * Asks Supabase Storage to mint a short-lived signed upload URL,
    using the server-side service-role key.
  * Validates the confirmation payload after the frontend uploads.
  * Upserts the `public.product_images` metadata row.

Hard rules (see docs/f2.22-contract-lock.md §§8, 8.1):

- The **service-role key is server-only**. It never leaves this module
  in a response body, is never logged, and never appears in an
  exception message. Errors raised here carry only an HTTP status code
  at most, mirroring `app.services.supabase_admin`.
- Direct Supabase writes by the `authenticated` role remain forbidden.
  Frontend uploads succeed only through the signed URL this service
  issues, and metadata writes go exclusively through the confirm
  endpoint that calls this service.
- The bucket is contractually `product-images` in F2.22.4. Any other
  bucket is rejected.

Supabase Storage endpoint used:
  POST {SUPABASE_URL}/storage/v1/object/upload/sign/{bucket}/{object_key}
"""

from __future__ import annotations

import re
import uuid
from typing import Final
from uuid import UUID

import httpx
from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_supabase_auth_settings
from app.db.models import Product
from app.db.models import ProductImage
from app.db.models import User
from app.schemas.products import ProductImageConfirmRequest
from app.schemas.products import ProductImageUploadUrlRequest
from app.schemas.products import ProductImageUploadUrlResponse


PRODUCT_IMAGES_BUCKET: Final[str] = "product-images"
ALLOWED_CONTENT_TYPES: Final[frozenset[str]] = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_CONTENT_TYPE_EXTENSIONS: Final[dict[str, str]] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_IMAGE_SIZE_BYTES: Final[int] = 5 * 1024 * 1024  # 5 MB
SIGNED_UPLOAD_TTL_SECONDS: Final[int] = 600  # 10 minutes
_REQUEST_TIMEOUT_SECONDS: Final[float] = 10.0

# Filenames the client sends are informational only — we never reuse
# the basename to build the object key. We still validate them so a
# wildly invalid value gets rejected early with a clear 400 rather
# than reaching Supabase.
_SAFE_FILENAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._ \-]{0,253}$"
)


class SupabaseStorageError(Exception):
    """Raised when a Supabase Storage call fails.

    Message is coarse and secret-free; the route maps it to a
    controlled 502/5xx response.
    """


# --------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------- #


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=detail
    )


def _validate_filename(filename: str) -> str:
    stripped = filename.strip()
    if not stripped:
        raise _bad_request("filename must not be empty.")
    if "/" in stripped or "\\" in stripped or ".." in stripped:
        raise _bad_request("filename contains unsafe characters.")
    if not _SAFE_FILENAME_RE.match(stripped):
        raise _bad_request("filename contains unsafe characters.")
    return stripped


def _validate_content_type(content_type: str) -> str:
    normalized = content_type.strip().lower()
    if normalized not in ALLOWED_CONTENT_TYPES:
        raise _bad_request(
            "content_type must be one of "
            f"{sorted(ALLOWED_CONTENT_TYPES)}."
        )
    return normalized


def _validate_size(size_bytes: int) -> int:
    if size_bytes <= 0:
        raise _bad_request("size_bytes must be positive.")
    if size_bytes > MAX_IMAGE_SIZE_BYTES:
        raise _bad_request(
            f"size_bytes exceeds the {MAX_IMAGE_SIZE_BYTES}-byte limit."
        )
    return size_bytes


def _validate_bucket(bucket: str) -> str:
    if bucket != PRODUCT_IMAGES_BUCKET:
        raise _bad_request(
            f"bucket must be '{PRODUCT_IMAGES_BUCKET}'."
        )
    return bucket


def _validate_object_key_for_product(
    object_key: str, product_id: UUID
) -> str:
    stripped = object_key.strip()
    if not stripped:
        raise _bad_request("object_key must not be empty.")
    if ".." in stripped or stripped.startswith("/"):
        raise _bad_request("object_key contains unsafe characters.")
    expected_prefix = f"products/{product_id}/"
    if not stripped.startswith(expected_prefix):
        raise _bad_request(
            "object_key does not belong to this product."
        )
    # Reject keys that are just the prefix with no leaf name.
    leaf = stripped[len(expected_prefix):]
    if not leaf or "/" in leaf:
        raise _bad_request("object_key is malformed.")
    return stripped


def _require_product(db: Session, product_id: UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    return product


# --------------------------------------------------------------------- #
# Object key generation
# --------------------------------------------------------------------- #


def _generate_object_key(product_id: UUID, content_type: str) -> str:
    """Build a per-product, collision-resistant object key.

    Format: ``products/<product_id>/<uuid4>.<ext>``. The UUID4 is
    drawn server-side so the client cannot influence the key. The
    extension is derived from the validated content type so the key
    suffix always matches the file type the client claimed (and that
    Supabase Storage was told to expect).
    """
    extension = _CONTENT_TYPE_EXTENSIONS[content_type]
    return f"products/{product_id}/{uuid.uuid4().hex}.{extension}"


# --------------------------------------------------------------------- #
# Supabase Storage HTTP call
# --------------------------------------------------------------------- #


def _require_storage_config() -> tuple[str, str]:
    """Return (base_url, service_role_key) or raise if unconfigured."""
    settings = get_supabase_auth_settings()
    base = settings.supabase_url.strip().rstrip("/")
    key = settings.supabase_service_role_key.strip()
    if not base:
        raise SupabaseStorageError("SUPABASE_URL is not configured")
    if not key:
        raise SupabaseStorageError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured"
        )
    return base, key


def _storage_headers(service_role_key: str) -> dict[str, str]:
    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }


def _request_signed_upload_url(
    bucket: str, object_key: str, expires_in_seconds: int
) -> str:
    """Ask Supabase Storage for a signed upload URL; return the absolute URL.

    The Supabase Storage REST API returns a relative ``url`` such as
    ``/object/upload/sign/<bucket>/<key>?token=<jwt>``. We prepend the
    project base so the frontend can use it directly or pass it to
    ``supabase.storage.from(...).uploadToSignedUrl(...)`` as-is.

    Raises :class:`SupabaseStorageError` on transport failure or non-2xx.
    The exception message never echoes the service-role key, the
    request URL, or the response body.
    """
    base, key = _require_storage_config()
    endpoint = (
        f"{base}/storage/v1/object/upload/sign/{bucket}/{object_key}"
    )
    try:
        response = httpx.post(
            endpoint,
            headers=_storage_headers(key),
            json={"expiresIn": expires_in_seconds},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise SupabaseStorageError(
            "Supabase Storage request failed during signed-upload mint"
        ) from exc

    if response.status_code not in (200, 201):
        raise SupabaseStorageError(
            "Supabase Storage returned status "
            f"{response.status_code} on signed-upload mint"
        )

    try:
        data = response.json()
        relative_url = str(data["url"])
    except (ValueError, KeyError, TypeError) as exc:
        raise SupabaseStorageError(
            "Supabase Storage returned an unexpected signed-upload response"
        ) from exc

    if relative_url.startswith("http://") or relative_url.startswith(
        "https://"
    ):
        return relative_url
    if not relative_url.startswith("/"):
        relative_url = "/" + relative_url
    return f"{base}/storage/v1{relative_url}"


def _request_object_delete(bucket: str, object_key: str) -> None:
    """Delete a single object from Supabase Storage.

    Mirrors :func:`_request_signed_upload_url`: uses the server-side
    service-role key and raises :class:`SupabaseStorageError` on
    transport failure or an unexpected non-2xx status. The exception
    message never echoes the service-role key, the request URL, or the
    response body.

    Supabase Storage endpoint:
      DELETE {SUPABASE_URL}/storage/v1/object/{bucket}/{object_key}

    A ``404`` (object already absent) is treated as success: the
    caller's intent — that the object no longer exist — is already
    satisfied, and failing on it would needlessly block metadata
    cleanup for an orphaned key.
    """
    base, key = _require_storage_config()
    endpoint = f"{base}/storage/v1/object/{bucket}/{object_key}"
    try:
        response = httpx.request(
            "DELETE",
            endpoint,
            headers=_storage_headers(key),
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise SupabaseStorageError(
            "Supabase Storage request failed during object delete"
        ) from exc

    if response.status_code == 404:
        return
    if response.status_code not in (200, 204):
        raise SupabaseStorageError(
            "Supabase Storage returned status "
            f"{response.status_code} on object delete"
        )


# --------------------------------------------------------------------- #
# Public entry points (used by the routes)
# --------------------------------------------------------------------- #


def create_product_image_upload_url(
    db: Session,
    product_id: UUID,
    payload: ProductImageUploadUrlRequest,
) -> ProductImageUploadUrlResponse:
    """Validate the request, generate the object key, and mint a signed URL.

    The product must exist. On any input violation a 400 HTTPException
    is raised. On a Supabase Storage transport/non-2xx error a
    :class:`SupabaseStorageError` is raised; the route maps that to a
    controlled 502 without leaking server-side details.
    """
    _require_product(db, product_id)

    _validate_filename(payload.filename)
    content_type = _validate_content_type(payload.content_type)
    _validate_size(payload.size_bytes)

    object_key = _generate_object_key(product_id, content_type)
    signed_url = _request_signed_upload_url(
        PRODUCT_IMAGES_BUCKET, object_key, SIGNED_UPLOAD_TTL_SECONDS
    )

    return ProductImageUploadUrlResponse(
        bucket=PRODUCT_IMAGES_BUCKET,
        object_key=object_key,
        signed_upload_url=signed_url,
        expires_in_seconds=SIGNED_UPLOAD_TTL_SECONDS,
    )


def confirm_product_image(
    db: Session,
    product_id: UUID,
    payload: ProductImageConfirmRequest,
    *,
    actor: User,
) -> ProductImage:
    """Upsert the metadata row for a product image, returning it.

    Enforces:
      * The product exists.
      * ``payload.bucket`` is the locked ``product-images`` bucket.
      * ``payload.object_key`` is well-formed and belongs to the same
        product prefix as ``product_id``.

    Because ``unique(product_id)`` enforces one primary image, this is
    a true upsert: an existing row's ``object_key`` and
    ``uploaded_by_user_id`` are overwritten in place rather than a new
    row being inserted. SQLAlchemy session flush guarantees a single
    row remains.
    """
    _require_product(db, product_id)
    _validate_bucket(payload.bucket)
    object_key = _validate_object_key_for_product(
        payload.object_key, product_id
    )

    existing = db.scalar(
        select(ProductImage).where(
            ProductImage.product_id == product_id
        )
    )
    old_object_key: str | None = None
    if existing is None:
        image = ProductImage(
            product_id=product_id,
            object_key=object_key,
            uploaded_by_user_id=actor.id,
        )
        db.add(image)
    else:
        # Capture the superseded object so it can be cleaned up AFTER
        # the new metadata is durably committed. Only a genuinely
        # different key needs cleanup — re-confirming the same key must
        # never delete the bytes we are keeping.
        if existing.object_key != object_key:
            old_object_key = existing.object_key
        existing.object_key = object_key
        existing.uploaded_by_user_id = actor.id
        image = existing

    db.commit()
    db.refresh(image)

    # Replace cleanup (best-effort). The new record is already durable
    # and valid; we never roll it back over a cleanup failure, since
    # that would discard a good upload. The old object is deleted only
    # after the commit, and a storage failure here leaves the old object
    # orphaned rather than turning a successful replacement into an
    # error. This best-effort posture is also why an unconfigured
    # storage backend (no SUPABASE_URL) does not break a confirm: the
    # raised SupabaseStorageError is swallowed below.
    if old_object_key is not None:
        try:
            _request_object_delete(PRODUCT_IMAGES_BUCKET, old_object_key)
        except SupabaseStorageError:
            pass

    return image


def delete_product_image(db: Session, product_id: UUID) -> Product:
    """Clear a product's primary image (metadata row + storage object).

    Admin-only at the route. Returns the product so the caller can
    serialize the updated ``primary_image: null`` state.

    Idempotent: if the product has no image, the product is returned
    unchanged (no storage call, no error) — clearing an already-clear
    product is a success, not a 404.

    Consistency strategy — *fail-hard*: the metadata row is deleted and
    flushed, then the storage object is removed; only if that storage
    delete succeeds is the transaction committed. If the storage delete
    fails the whole operation is rolled back, so the metadata row and
    the storage object stay in sync (both remain) rather than leaving a
    split-brain where the row is gone but the bytes linger. This differs
    from the replace path in :func:`confirm_product_image`, where a new
    desired record already exists and must be preserved; here there is
    no new state to protect, so all-or-nothing is the safer choice.
    """
    product = _require_product(db, product_id)

    existing = db.scalar(
        select(ProductImage).where(
            ProductImage.product_id == product_id
        )
    )
    if existing is None:
        # Nothing to delete and nothing to clean up — idempotent no-op.
        return product

    object_key = existing.object_key
    db.delete(existing)
    db.flush()  # stage the row removal without committing yet

    try:
        _request_object_delete(PRODUCT_IMAGES_BUCKET, object_key)
    except SupabaseStorageError:
        # Storage cleanup failed — roll back the metadata removal so the
        # DB and storage stay consistent, and surface the failure so the
        # route can return a controlled 502.
        db.rollback()
        raise

    db.commit()
    db.refresh(product)
    return product
