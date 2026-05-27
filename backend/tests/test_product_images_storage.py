"""F2.22.4.F — backend storage service + signed upload endpoints.

Covers:
  * POST /products/{id}/image-upload-url
  * POST /products/{id}/images
  * Underlying app.services.storage helpers

Supabase Storage HTTP calls are mocked through
``app.services.storage._request_signed_upload_url``. The service-role
key is never present in any response body and is never required to be
configured for the tests to pass.
"""
from __future__ import annotations

import re
import uuid
from typing import Callable

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductImage
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services import storage as storage_svc
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        store = Store(name="Img-QA", code=f"is-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session, make_store) -> Callable[..., User]:
    def _create(role: UserRole) -> User:
        store_id = None if role == UserRole.admin else make_store().id
        return central_make_user(
            db_session,
            role=role,
            store_id=store_id,
            full_name=f"Img {role.value}",
            is_active=True,
        )

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(**overrides) -> Product:
        product = Product(
            name=overrides.get(
                "name", f"Img-{uuid.uuid4().hex[:6]}"
            ),
            category=overrides.get("category", "vape"),
            compliance_status=overrides.get(
                "compliance_status", ComplianceStatus.allowed
            ),
            allowed_for_sale=overrides.get("allowed_for_sale", True),
            is_active=overrides.get("is_active", True),
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


@pytest.fixture
def stub_signed_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, list[tuple[str, str, int]]]:
    """Replace the Supabase Storage HTTP call with a deterministic stub.

    Records every (bucket, object_key, ttl) triple and returns a
    canned signed URL. Tests inspect ``calls`` to assert what was
    sent without touching the network or needing real credentials.
    """
    record: dict[str, list[tuple[str, str, int]]] = {"calls": []}

    def _fake(bucket: str, object_key: str, expires_in_seconds: int) -> str:
        record["calls"].append((bucket, object_key, expires_in_seconds))
        return (
            "https://example.supabase.co/storage/v1/object/upload/sign/"
            f"{bucket}/{object_key}?token=FAKE-SIGNED-TOKEN"
        )

    monkeypatch.setattr(
        storage_svc, "_request_signed_upload_url", _fake
    )
    return record


def _valid_upload_payload(**overrides) -> dict:
    payload = {
        "filename": "hero.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 12345,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Service unit tests (no HTTP)
# ---------------------------------------------------------------------------


class TestStorageServiceHelpers:
    def test_generate_object_key_uses_product_prefix_and_extension(self) -> None:
        product_id = uuid.uuid4()
        key = storage_svc._generate_object_key(product_id, "image/png")
        assert key.startswith(f"products/{product_id}/")
        assert key.endswith(".png")
        # The middle segment is a uuid hex.
        leaf = key.split("/")[-1]
        assert re.match(r"^[0-9a-f]{32}\.png$", leaf)

    @pytest.mark.parametrize(
        "content_type,expected_extension",
        [
            ("image/jpeg", "jpg"),
            ("image/png", "png"),
            ("image/webp", "webp"),
        ],
    )
    def test_object_key_extension_matches_content_type(
        self, content_type: str, expected_extension: str
    ) -> None:
        key = storage_svc._generate_object_key(
            uuid.uuid4(), content_type
        )
        assert key.endswith(f".{expected_extension}")

    def test_object_keys_are_collision_resistant(self) -> None:
        product_id = uuid.uuid4()
        keys = {
            storage_svc._generate_object_key(product_id, "image/jpeg")
            for _ in range(50)
        }
        assert len(keys) == 50

    def test_request_signed_upload_url_wraps_transport_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
        from app.core.config import get_supabase_auth_settings

        get_supabase_auth_settings.cache_clear()

        def _raise(*_args, **_kwargs):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(storage_svc.httpx, "post", _raise)

        with pytest.raises(storage_svc.SupabaseStorageError) as excinfo:
            storage_svc._request_signed_upload_url(
                "product-images", "products/abc/x.png", 600
            )
        # The exception message must not echo the service-role key.
        assert "fake-key" not in str(excinfo.value)
        get_supabase_auth_settings.cache_clear()

    def test_request_signed_upload_url_wraps_non_2xx(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
        from app.core.config import get_supabase_auth_settings

        get_supabase_auth_settings.cache_clear()

        class _FakeResponse:
            status_code = 500

            def json(self) -> dict:
                return {}

        monkeypatch.setattr(
            storage_svc.httpx, "post", lambda *_a, **_kw: _FakeResponse()
        )

        with pytest.raises(storage_svc.SupabaseStorageError) as excinfo:
            storage_svc._request_signed_upload_url(
                "product-images", "products/abc/x.png", 600
            )
        msg = str(excinfo.value)
        assert "fake-key" not in msg
        assert "500" in msg
        get_supabase_auth_settings.cache_clear()


# ---------------------------------------------------------------------------
# Upload URL endpoint
# ---------------------------------------------------------------------------


class TestImageUploadUrlEndpoint:
    URL = "/products/{pid}/image-upload-url"

    def test_anonymous_blocked(
        self, client: TestClient, make_product: Callable[..., Product]
    ) -> None:
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id), json=_valid_upload_payload()
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_blocked(
        self,
        client: TestClient,
        make_user,
        make_product,
        role: UserRole,
    ) -> None:
        actor = make_user(role)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(),
            headers=_auth(actor),
        )
        assert resp.status_code == 403

    def test_admin_success_returns_signed_url_shape(
        self,
        client: TestClient,
        make_user,
        make_product,
        stub_signed_upload,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(content_type="image/png"),
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {
            "bucket",
            "object_key",
            "signed_upload_url",
            "expires_in_seconds",
        }
        assert body["bucket"] == "product-images"
        assert body["object_key"].startswith(
            f"products/{prod.id}/"
        )
        assert body["object_key"].endswith(".png")
        assert body["expires_in_seconds"] > 0
        assert body["signed_upload_url"].startswith(
            "https://example.supabase.co/"
        )

        # Stub was called with the same bucket + object_key + ttl.
        assert len(stub_signed_upload["calls"]) == 1
        called_bucket, called_key, called_ttl = stub_signed_upload["calls"][0]
        assert called_bucket == "product-images"
        assert called_key == body["object_key"]
        assert called_ttl == body["expires_in_seconds"]

    def test_unknown_product_returns_404(
        self,
        client: TestClient,
        make_user,
        stub_signed_upload,
    ) -> None:
        admin = make_user(UserRole.admin)
        resp = client.post(
            self.URL.format(pid=uuid.uuid4()),
            json=_valid_upload_payload(),
            headers=_auth(admin),
        )
        assert resp.status_code == 404
        # The service-side stub must not have been called for a 404.
        assert stub_signed_upload["calls"] == []

    @pytest.mark.parametrize(
        "bad_content_type",
        ["image/gif", "application/pdf", "text/plain", "image/svg+xml"],
    )
    def test_invalid_content_type_rejected(
        self,
        client: TestClient,
        make_user,
        make_product,
        stub_signed_upload,
        bad_content_type: str,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(content_type=bad_content_type),
            headers=_auth(admin),
        )
        assert resp.status_code in (400, 422)
        assert stub_signed_upload["calls"] == []

    def test_oversized_file_rejected(
        self,
        client: TestClient,
        make_user,
        make_product,
        stub_signed_upload,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(
                size_bytes=storage_svc.MAX_IMAGE_SIZE_BYTES + 1
            ),
            headers=_auth(admin),
        )
        assert resp.status_code in (400, 422)
        assert stub_signed_upload["calls"] == []

    @pytest.mark.parametrize(
        "bad_filename",
        ["", " ", "..", "../etc/passwd", "a/b.jpg", "x\\y.png", "\x00.png"],
    )
    def test_unsafe_filename_rejected(
        self,
        client: TestClient,
        make_user,
        make_product,
        stub_signed_upload,
        bad_filename: str,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(filename=bad_filename),
            headers=_auth(admin),
        )
        assert resp.status_code in (400, 422)
        assert stub_signed_upload["calls"] == []

    def test_response_never_contains_service_role_key(
        self,
        client: TestClient,
        make_user,
        make_product,
        stub_signed_upload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Set a recognizable fake service-role key to scan for.
        monkeypatch.setenv(
            "SUPABASE_SERVICE_ROLE_KEY", "SROLE-CANARY-VALUE"
        )
        from app.core.config import get_supabase_auth_settings

        get_supabase_auth_settings.cache_clear()

        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(),
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        assert "SROLE-CANARY-VALUE" not in resp.text

        get_supabase_auth_settings.cache_clear()

    def test_response_never_contains_authorization_or_apikey_headers(
        self,
        client: TestClient,
        make_user,
        make_product,
        stub_signed_upload,
    ) -> None:
        # F2.22.4.H: belt-and-braces — the upload-URL response carries
        # only the fields documented in the contract. The server-side
        # Supabase REST headers (`Authorization: Bearer <service-role>`
        # and `apikey: <service-role>`) must never appear in any form.
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(),
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        text = resp.text
        # Scan as substrings — case-insensitive against the raw body —
        # so a leaked header name surfaces regardless of casing.
        lowered = text.lower()
        assert "authorization" not in lowered
        assert "apikey" not in lowered
        # And the response keys are exactly the contract.
        assert set(resp.json().keys()) == {
            "bucket",
            "object_key",
            "signed_upload_url",
            "expires_in_seconds",
        }

    def test_upstream_storage_failure_returns_502_without_leaking(
        self,
        client: TestClient,
        make_user,
        make_product,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(
            "SUPABASE_SERVICE_ROLE_KEY", "SROLE-FAILURE-CANARY"
        )
        from app.core.config import get_supabase_auth_settings

        get_supabase_auth_settings.cache_clear()

        def _raise(*_a, **_kw):
            raise storage_svc.SupabaseStorageError(
                "Supabase Storage returned status 500 on signed-upload mint"
            )

        monkeypatch.setattr(
            storage_svc, "_request_signed_upload_url", _raise
        )

        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_valid_upload_payload(),
            headers=_auth(admin),
        )
        assert resp.status_code == 502
        assert "SROLE-FAILURE-CANARY" not in resp.text

        get_supabase_auth_settings.cache_clear()


# ---------------------------------------------------------------------------
# Confirm endpoint
# ---------------------------------------------------------------------------


def _confirm_payload(product_id: uuid.UUID, *, key: str | None = None) -> dict:
    return {
        "bucket": "product-images",
        "object_key": key
        or f"products/{product_id}/{uuid.uuid4().hex}.jpg",
    }


class TestImageConfirmEndpoint:
    URL = "/products/{pid}/images"

    def test_anonymous_blocked(
        self, client: TestClient, make_product: Callable[..., Product]
    ) -> None:
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id), json=_confirm_payload(prod.id)
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_blocked(
        self,
        client: TestClient,
        make_user,
        make_product,
        role: UserRole,
    ) -> None:
        actor = make_user(role)
        prod = make_product()
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=_confirm_payload(prod.id),
            headers=_auth(actor),
        )
        assert resp.status_code == 403

    def test_admin_can_confirm_and_set_uploaded_by(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_product,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        payload = _confirm_payload(prod.id)
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=payload,
            headers=_auth(admin),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["product_id"] == str(prod.id)
        assert body["object_key"] == payload["object_key"]
        assert body["uploaded_by_user_id"] == str(admin.id)
        assert "public_url" in body  # computed field present (may be None)

    def test_unknown_product_returns_404(
        self,
        client: TestClient,
        make_user,
    ) -> None:
        admin = make_user(UserRole.admin)
        missing = uuid.uuid4()
        resp = client.post(
            self.URL.format(pid=missing),
            json=_confirm_payload(missing),
            headers=_auth(admin),
        )
        assert resp.status_code == 404

    def test_invalid_bucket_rejected(
        self,
        client: TestClient,
        make_user,
        make_product,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        payload = _confirm_payload(prod.id)
        payload["bucket"] = "store-assets"
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=payload,
            headers=_auth(admin),
        )
        assert resp.status_code == 400

    def test_object_key_for_other_product_rejected(
        self,
        client: TestClient,
        make_user,
        make_product,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        other_product_id = uuid.uuid4()
        payload = {
            "bucket": "product-images",
            "object_key": f"products/{other_product_id}/{uuid.uuid4().hex}.jpg",
        }
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=payload,
            headers=_auth(admin),
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize(
        "bad_key_factory",
        [
            lambda pid: "",
            lambda pid: "../escape.jpg",
            lambda pid: "/products/" + str(pid) + "/x.jpg",
            lambda pid: f"products/{pid}/",
            lambda pid: f"products/{pid}/nested/path.jpg",
            lambda pid: f"other-prefix/{pid}/x.jpg",
        ],
    )
    def test_malformed_object_key_rejected(
        self,
        client: TestClient,
        make_user,
        make_product,
        bad_key_factory,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        payload = {
            "bucket": "product-images",
            "object_key": bad_key_factory(prod.id),
        }
        resp = client.post(
            self.URL.format(pid=prod.id),
            json=payload,
            headers=_auth(admin),
        )
        assert resp.status_code in (400, 422)

    def test_repeated_confirmation_upserts_not_duplicates(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_product,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()

        first_key = f"products/{prod.id}/{uuid.uuid4().hex}.jpg"
        second_key = f"products/{prod.id}/{uuid.uuid4().hex}.png"

        r1 = client.post(
            self.URL.format(pid=prod.id),
            json={"bucket": "product-images", "object_key": first_key},
            headers=_auth(admin),
        )
        r2 = client.post(
            self.URL.format(pid=prod.id),
            json={"bucket": "product-images", "object_key": second_key},
            headers=_auth(admin),
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json()["object_key"] == second_key

        # Exactly one row remains for this product.
        rows = list(
            db_session.scalars(
                select(ProductImage).where(
                    ProductImage.product_id == prod.id
                )
            )
        )
        assert len(rows) == 1
        assert rows[0].object_key == second_key

    def test_product_read_exposes_primary_image_after_confirm(
        self,
        client: TestClient,
        make_user,
        make_product,
    ) -> None:
        admin = make_user(UserRole.admin)
        prod = make_product()
        key = f"products/{prod.id}/{uuid.uuid4().hex}.webp"

        confirm = client.post(
            self.URL.format(pid=prod.id),
            json={"bucket": "product-images", "object_key": key},
            headers=_auth(admin),
        )
        assert confirm.status_code == 201

        detail = client.get(
            f"/products/{prod.id}", headers=_auth(admin)
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["primary_image"] is not None
        assert body["primary_image"]["object_key"] == key
        assert body["primary_image"]["uploaded_by_user_id"] == str(
            admin.id
        )
