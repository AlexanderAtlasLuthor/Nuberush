import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.core.security import hash_password
from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        store = Store(name="Prod-QA", code=f"pq-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session, make_store) -> Callable[..., User]:
    def _create(role: UserRole) -> User:
        store_id = None if role == UserRole.admin else make_store().id
        user = User(
            full_name=f"Prod {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("supersecret123"),
            role=role,
            store_id=store_id,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        name: str | None = None,
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
        is_active: bool = True,
    ) -> Product:
        product = Product(
            name=name or f"Prod-{uuid.uuid4().hex[:6]}",
            category="vape",
            compliance_status=compliance_status,
            allowed_for_sale=allowed_for_sale,
            is_active=is_active,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _product_payload(**overrides) -> dict:
    payload = {
        "name": f"Elf-{uuid.uuid4().hex[:6]}",
        "brand": "Elf",
        "category": "vape",
        "description": "test",
        "jurisdiction": "FL",
    }
    payload.update(overrides)
    return payload


def _variant_payload(product_id: uuid.UUID, **overrides) -> dict:
    payload = {
        "product_id": str(product_id),
        "sku": f"SKU-{uuid.uuid4().hex[:8]}",
        "barcode": f"BC-{uuid.uuid4().hex[:8]}",
        "flavor": "watermelon",
        "price": "9.99",
        "cost": "4.00",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Reads — anyone authenticated can read; anonymous is rejected
# ---------------------------------------------------------------------------


class TestProductReadAccess:
    def test_anonymous_list_returns_401(self, client: TestClient):
        resp = client.get("/products")
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.admin,
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_each_role_can_list_products(
        self, client: TestClient, make_user, role: UserRole
    ):
        user = make_user(role)
        resp = client.get("/products", headers=_auth(user))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_product_detail_returns_full_shape(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product(name="Detail Probe")
        resp = client.get(f"/products/{prod.id}", headers=_auth(admin))
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {
            "id",
            "name",
            "brand",
            "category",
            "description",
            "compliance_status",
            "allowed_for_sale",
            "is_active",
            "hold_reason",
            "jurisdiction",
            "last_compliance_check",
            "approval_status",
            "proposed_by_store_id",
            "proposed_by_user_id",
            "reviewed_by_user_id",
            "reviewed_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        }

    def test_get_unknown_product_returns_404(
        self, client: TestClient, make_user
    ):
        user = make_user(UserRole.staff)
        resp = client.get(
            f"/products/{uuid.uuid4()}", headers=_auth(user)
        )
        assert resp.status_code == 404

    def test_driver_can_list_variants(
        self, client: TestClient, make_user, make_product
    ):
        driver = make_user(UserRole.driver)
        prod = make_product()
        resp = client.get(
            f"/products/{prod.id}/variants", headers=_auth(driver)
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Product create — admin only
# ---------------------------------------------------------------------------


class TestProductCreate:
    def test_admin_creates_product(self, client: TestClient, make_user):
        admin = make_user(UserRole.admin)
        resp = client.post(
            "/products", json=_product_payload(), headers=_auth(admin)
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["compliance_status"] == "allowed"
        assert body["allowed_for_sale"] is True
        assert body["is_active"] is True
        # Admin-created rows are approved immediately and record the
        # admin as the reviewer (so the audit field is never empty for
        # rows that bypass the proposal queue).
        assert body["approval_status"] == "approved"
        assert body["reviewed_by_user_id"] == str(admin.id)
        assert body["reviewed_at"] is not None
        assert body["proposed_by_store_id"] is None
        assert body["proposed_by_user_id"] is None

    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.post("/products", json=_product_payload())
        assert resp.status_code == 401

    @pytest.mark.parametrize("role", [UserRole.owner, UserRole.manager])
    def test_manager_or_owner_creates_pending_proposal(
        self, client: TestClient, make_user, role: UserRole
    ):
        user = make_user(role)
        resp = client.post(
            "/products",
            json=_product_payload(),
            headers=_auth(user),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["approval_status"] == "pending"
        assert body["proposed_by_store_id"] == str(user.store_id)
        assert body["proposed_by_user_id"] == str(user.id)
        assert body["reviewed_by_user_id"] is None
        assert body["reviewed_at"] is None
        assert body["rejection_reason"] is None
        # Store-proposed rows always land with conservative compliance
        # defaults regardless of what the client tried to send.
        assert body["compliance_status"] == "allowed"
        assert body["allowed_for_sale"] is True

    def test_store_proposal_ignores_client_compliance_overrides(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        resp = client.post(
            "/products",
            json=_product_payload(
                compliance_status="restricted", allowed_for_sale=False
            ),
            headers=_auth(manager),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["compliance_status"] == "allowed"
        assert body["allowed_for_sale"] is True

    @pytest.mark.parametrize(
        "role",
        [UserRole.staff, UserRole.driver],
    )
    def test_staff_and_driver_still_blocked(
        self, client: TestClient, make_user, role: UserRole
    ):
        user = make_user(role)
        resp = client.post(
            "/products", json=_product_payload(), headers=_auth(user)
        )
        assert resp.status_code == 403

    def test_banned_with_allowed_for_sale_true_is_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.post(
            "/products",
            json=_product_payload(
                compliance_status="banned", allowed_for_sale=True
            ),
            headers=_auth(admin),
        )
        assert resp.status_code == 422

    def test_empty_name_is_422(self, client: TestClient, make_user):
        admin = make_user(UserRole.admin)
        resp = client.post(
            "/products",
            json=_product_payload(name="   "),
            headers=_auth(admin),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Product update — admin only
# ---------------------------------------------------------------------------


class TestProductUpdate:
    def test_admin_updates_non_compliance_fields(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.patch(
            f"/products/{prod.id}",
            json={"brand": "Renamed", "description": "updated"},
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["brand"] == "Renamed"
        assert resp.json()["compliance_status"] == "allowed"

    def test_compliance_fields_are_silently_dropped_from_patch(
        self, client: TestClient, make_user, make_product
    ):
        # Pydantic defaults to extra="ignore", so unknown fields in the
        # ProductUpdate body are dropped. The compliance state must NOT
        # change through this endpoint.
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.patch(
            f"/products/{prod.id}",
            json={"compliance_status": "banned", "allowed_for_sale": False},
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["compliance_status"] == "allowed"
        assert resp.json()["allowed_for_sale"] is True

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
        self, client: TestClient, make_user, make_product, role: UserRole
    ):
        user = make_user(role)
        prod = make_product()
        resp = client.patch(
            f"/products/{prod.id}",
            json={"brand": "x"},
            headers=_auth(user),
        )
        assert resp.status_code == 403

    def test_unknown_product_is_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.patch(
            f"/products/{uuid.uuid4()}",
            json={"brand": "x"},
            headers=_auth(admin),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Product delete — admin only, soft default + hard via query
# ---------------------------------------------------------------------------


class TestProductDelete:
    def test_admin_soft_delete(
        self, client: TestClient, make_user, make_product, db_session
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.delete(
            f"/products/{prod.id}", headers=_auth(admin)
        )
        assert resp.status_code == 204
        # Product still exists, is_active=False
        db_session.expire_all()
        reloaded = db_session.get(Product, prod.id)
        assert reloaded is not None
        assert reloaded.is_active is False

    def test_admin_hard_delete(
        self, client: TestClient, make_user, make_product, db_session
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        pid = prod.id
        resp = client.delete(
            f"/products/{pid}?hard=true", headers=_auth(admin)
        )
        assert resp.status_code == 204
        db_session.expire_all()
        assert db_session.get(Product, pid) is None

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
        self, client: TestClient, make_user, make_product, role: UserRole
    ):
        user = make_user(role)
        prod = make_product()
        resp = client.delete(
            f"/products/{prod.id}", headers=_auth(user)
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Variant create — admin only, 409 on dup, 404 on missing parent
# ---------------------------------------------------------------------------


class TestVariantCreate:
    def test_admin_creates_variant(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            f"/products/{prod.id}/variants",
            json=_variant_payload(prod.id),
            headers=_auth(admin),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["product_id"] == str(prod.id)
        assert body["price"] == "9.99"

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
        self, client: TestClient, make_user, make_product, role: UserRole
    ):
        user = make_user(role)
        prod = make_product()
        resp = client.post(
            f"/products/{prod.id}/variants",
            json=_variant_payload(prod.id),
            headers=_auth(user),
        )
        assert resp.status_code == 403

    def test_unknown_parent_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        ghost = uuid.uuid4()
        resp = client.post(
            f"/products/{ghost}/variants",
            json=_variant_payload(ghost),
            headers=_auth(admin),
        )
        assert resp.status_code == 404

    def test_path_body_mismatch_is_400(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod_a = make_product()
        prod_b = make_product()
        resp = client.post(
            f"/products/{prod_a.id}/variants",
            json=_variant_payload(prod_b.id),  # body says other parent
            headers=_auth(admin),
        )
        assert resp.status_code == 400
        assert "match" in resp.json()["detail"].lower()

    def test_duplicate_sku_returns_409(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        sku = f"SKU-{uuid.uuid4().hex[:8]}"
        first = _variant_payload(prod.id, sku=sku)
        resp = client.post(
            f"/products/{prod.id}/variants",
            json=first,
            headers=_auth(admin),
        )
        assert resp.status_code == 201
        # Second attempt with same SKU on a different barcode + product
        prod2 = make_product()
        dup = _variant_payload(prod2.id, sku=sku)
        resp = client.post(
            f"/products/{prod2.id}/variants",
            json=dup,
            headers=_auth(admin),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "SKU already exists."

    def test_duplicate_barcode_returns_409(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        barcode = f"BC-{uuid.uuid4().hex[:8]}"
        first = _variant_payload(prod.id, barcode=barcode)
        resp = client.post(
            f"/products/{prod.id}/variants",
            json=first,
            headers=_auth(admin),
        )
        assert resp.status_code == 201
        prod2 = make_product()
        dup = _variant_payload(prod2.id, barcode=barcode)
        resp = client.post(
            f"/products/{prod2.id}/variants",
            json=dup,
            headers=_auth(admin),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Barcode already exists."

    def test_negative_price_is_422(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.post(
            f"/products/{prod.id}/variants",
            json=_variant_payload(prod.id, price="-1.00"),
            headers=_auth(admin),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Variant update / delete — admin only
# ---------------------------------------------------------------------------


class TestVariantUpdateAndDelete:
    def _make_variant(
        self, db_session, make_product
    ) -> ProductVariant:
        prod = make_product()
        v = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            barcode=f"BC-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
        )
        db_session.add(v)
        db_session.commit()
        db_session.refresh(v)
        return v

    def test_admin_updates_variant_price(
        self, client: TestClient, make_user, make_product, db_session
    ):
        admin = make_user(UserRole.admin)
        v = self._make_variant(db_session, make_product)
        resp = client.patch(
            f"/variants/{v.id}",
            json={"price": "12.50"},
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["price"] == "12.50"

    def test_admin_soft_deletes_variant(
        self, client: TestClient, make_user, make_product, db_session
    ):
        admin = make_user(UserRole.admin)
        v = self._make_variant(db_session, make_product)
        resp = client.delete(
            f"/variants/{v.id}", headers=_auth(admin)
        )
        assert resp.status_code == 204
        db_session.expire_all()
        reloaded = db_session.get(ProductVariant, v.id)
        assert reloaded is not None and reloaded.is_active is False

    def test_admin_hard_deletes_variant(
        self, client: TestClient, make_user, make_product, db_session
    ):
        admin = make_user(UserRole.admin)
        v = self._make_variant(db_session, make_product)
        vid = v.id
        resp = client.delete(
            f"/variants/{vid}?hard=true", headers=_auth(admin)
        )
        assert resp.status_code == 204
        db_session.expire_all()
        assert db_session.get(ProductVariant, vid) is None

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_cannot_update(
        self,
        client: TestClient,
        make_user,
        make_product,
        db_session,
        role: UserRole,
    ):
        user = make_user(role)
        v = self._make_variant(db_session, make_product)
        resp = client.patch(
            f"/variants/{v.id}",
            json={"price": "10.00"},
            headers=_auth(user),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Compliance — admin only, audit log written, transitions
# ---------------------------------------------------------------------------


class TestProductCompliance:
    def test_admin_changes_compliance_writes_audit(
        self, client: TestClient, make_user, make_product, db_session
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.patch(
            f"/products/{prod.id}/compliance",
            json={
                "compliance_status": "banned",
                "allowed_for_sale": False,
                "reason": "Regulator ban",
            },
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["compliance_status"] == "banned"
        assert body["allowed_for_sale"] is False
        assert body["last_compliance_check"] is not None
        # Audit row written in the same transaction
        db_session.expire_all()
        audits = list(
            db_session.scalars(
                select(ProductComplianceAuditLog).where(
                    ProductComplianceAuditLog.product_id == prod.id
                )
            ).all()
        )
        assert len(audits) == 1
        a = audits[0]
        assert a.previous_compliance_status == ComplianceStatus.allowed
        assert a.new_compliance_status == ComplianceStatus.banned
        assert a.reason == "Regulator ban"
        assert a.changed_by_user_id == admin.id

    def test_banned_with_allowed_for_sale_true_is_422(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.patch(
            f"/products/{prod.id}/compliance",
            json={
                "compliance_status": "banned",
                "allowed_for_sale": True,
                "reason": "x",
            },
            headers=_auth(admin),
        )
        assert resp.status_code == 422

    def test_empty_reason_is_422(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        resp = client.patch(
            f"/products/{prod.id}/compliance",
            json={
                "compliance_status": "allowed",
                "allowed_for_sale": True,
                "reason": "   ",
            },
            headers=_auth(admin),
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_cannot_change_compliance(
        self,
        client: TestClient,
        make_user,
        make_product,
        role: UserRole,
    ):
        user = make_user(role)
        prod = make_product()
        resp = client.patch(
            f"/products/{prod.id}/compliance",
            json={
                "compliance_status": "allowed",
                "allowed_for_sale": True,
                "reason": "x",
            },
            headers=_auth(user),
        )
        assert resp.status_code == 403


class TestProductComplianceAudit:
    def test_admin_lists_audit_rows(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(UserRole.admin)
        prod = make_product()
        # Two compliance changes
        for status_, allowed in (("banned", False), ("allowed", True)):
            resp = client.patch(
                f"/products/{prod.id}/compliance",
                json={
                    "compliance_status": status_,
                    "allowed_for_sale": allowed,
                    "reason": f"transition to {status_}",
                },
                headers=_auth(admin),
            )
            assert resp.status_code == 200
        resp = client.get(
            f"/products/{prod.id}/compliance-audit",
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        # The conftest wraps every test in a single outer transaction, so
        # PostgreSQL now() returns the same timestamp for both audit rows;
        # we can't rely on created_at ordering inside one test. Assert both
        # transitions are present without ordering.
        transitions = {
            (r["previous_compliance_status"], r["new_compliance_status"])
            for r in rows
        }
        assert ("allowed", "banned") in transitions
        assert ("banned", "allowed") in transitions

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_cannot_list_audit(
        self, client: TestClient, make_user, make_product, role: UserRole
    ):
        user = make_user(role)
        prod = make_product()
        resp = client.get(
            f"/products/{prod.id}/compliance-audit",
            headers=_auth(user),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Sellability endpoint — wraps assert_product_sellable
# ---------------------------------------------------------------------------


class TestProductSellability:
    def test_sellable_product_returns_200(
        self, client: TestClient, make_user, make_product
    ):
        user = make_user(UserRole.staff)
        prod = make_product()
        resp = client.get(
            f"/products/{prod.id}/sellable", headers=_auth(user)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sellable"] is True
        assert body["product_id"] == str(prod.id)

    def test_banned_product_returns_422(
        self, client: TestClient, make_user, make_product
    ):
        user = make_user(UserRole.staff)
        prod = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        resp = client.get(
            f"/products/{prod.id}/sellable", headers=_auth(user)
        )
        assert resp.status_code == 422
        assert "banned" in resp.json()["detail"].lower()

    def test_inactive_product_returns_422(
        self, client: TestClient, make_user, make_product
    ):
        user = make_user(UserRole.staff)
        prod = make_product(is_active=False)
        resp = client.get(
            f"/products/{prod.id}/sellable", headers=_auth(user)
        )
        assert resp.status_code == 422
        assert "is_active" in resp.json()["detail"]

    def test_kill_switch_returns_422(
        self, client: TestClient, make_user, make_product
    ):
        user = make_user(UserRole.staff)
        prod = make_product(allowed_for_sale=False)
        resp = client.get(
            f"/products/{prod.id}/sellable", headers=_auth(user)
        )
        assert resp.status_code == 422
        assert "allowed_for_sale" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Approval workflow — admin approves / rejects store-proposed products
# ---------------------------------------------------------------------------


def _propose_product(client: TestClient, proposer: User) -> dict:
    """Helper: store-side POST that returns the response body."""
    resp = client.post(
        "/products",
        json=_product_payload(name=f"Proposal-{uuid.uuid4().hex[:6]}"),
        headers=_auth(proposer),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestProductApprovalActions:
    def test_admin_approves_pending_product(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        admin = make_user(UserRole.admin)
        proposal = _propose_product(client, manager)
        assert proposal["approval_status"] == "pending"

        resp = client.post(
            f"/products/{proposal['id']}/approve",
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["approval_status"] == "approved"
        assert body["reviewed_by_user_id"] == str(admin.id)
        assert body["reviewed_at"] is not None
        assert body["rejection_reason"] is None

    def test_admin_rejects_with_reason(
        self, client: TestClient, make_user
    ):
        owner = make_user(UserRole.owner)
        admin = make_user(UserRole.admin)
        proposal = _propose_product(client, owner)

        resp = client.post(
            f"/products/{proposal['id']}/reject",
            json={"reason": "Duplicate of existing SKU family"},
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["approval_status"] == "rejected"
        assert body["rejection_reason"] == "Duplicate of existing SKU family"
        assert body["reviewed_by_user_id"] == str(admin.id)

    def test_rejection_requires_reason(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        admin = make_user(UserRole.admin)
        proposal = _propose_product(client, manager)

        resp = client.post(
            f"/products/{proposal['id']}/reject",
            json={"reason": "   "},
            headers=_auth(admin),
        )
        assert resp.status_code == 422

    def test_re_approving_rejected_clears_reason(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        admin = make_user(UserRole.admin)
        proposal = _propose_product(client, manager)
        client.post(
            f"/products/{proposal['id']}/reject",
            json={"reason": "Too risky for now"},
            headers=_auth(admin),
        )

        resp = client.post(
            f"/products/{proposal['id']}/approve",
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["rejection_reason"] is None
        assert resp.json()["approval_status"] == "approved"

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_cannot_approve(
        self, client: TestClient, make_user, role: UserRole
    ):
        manager = make_user(UserRole.manager)
        proposal = _propose_product(client, manager)
        actor = make_user(role)
        resp = client.post(
            f"/products/{proposal['id']}/approve",
            headers=_auth(actor),
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_cannot_reject(
        self, client: TestClient, make_user, role: UserRole
    ):
        manager = make_user(UserRole.manager)
        proposal = _propose_product(client, manager)
        actor = make_user(role)
        resp = client.post(
            f"/products/{proposal['id']}/reject",
            json={"reason": "nope"},
            headers=_auth(actor),
        )
        assert resp.status_code == 403

    def test_approve_unknown_product_is_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.post(
            f"/products/{uuid.uuid4()}/approve",
            headers=_auth(admin),
        )
        assert resp.status_code == 404


class TestProductListVisibility:
    """Pending proposals are scoped per-store; admin sees everything."""

    def test_other_stores_do_not_see_my_pending_proposal(
        self, client: TestClient, make_user, db_session
    ):
        store_a_manager = make_user(UserRole.manager)
        _propose_product(client, store_a_manager)

        store_b_manager = make_user(UserRole.manager)
        resp = client.get("/products", headers=_auth(store_b_manager))
        assert resp.status_code == 200
        items = resp.json()
        # Store B sees no items because only one product exists and it
        # belongs to store A's pending queue.
        assert all(p["approval_status"] == "approved" for p in items)
        assert all(
            p["proposed_by_store_id"] != str(store_a_manager.store_id)
            for p in items
        )

    def test_owner_sees_own_store_pending(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        proposal = _propose_product(client, manager)

        resp = client.get("/products", headers=_auth(manager))
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert proposal["id"] in ids

    def test_admin_sees_all_pending(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        _propose_product(client, manager)

        admin = make_user(UserRole.admin)
        resp = client.get(
            "/products?approval_status=pending",
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        assert all(p["approval_status"] == "pending" for p in items)

    def test_pending_product_is_not_sellable(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        proposal = _propose_product(client, manager)
        resp = client.get(
            f"/products/{proposal['id']}/sellable",
            headers=_auth(manager),
        )
        assert resp.status_code == 422
        assert "approval_status" in resp.json()["detail"]

    def test_only_sellable_excludes_pending(
        self, client: TestClient, make_user
    ):
        manager = make_user(UserRole.manager)
        _propose_product(client, manager)

        resp = client.get(
            "/products?only_sellable=true",
            headers=_auth(manager),
        )
        assert resp.status_code == 200
        statuses = {p["approval_status"] for p in resp.json()}
        assert "pending" not in statuses
        assert "rejected" not in statuses
