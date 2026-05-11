"""API-level tests for the unified store audit feed (F2.16.3).

Exercises GET /stores/{store_id}/audit via TestClient. Schema
validation (F2.16.1) and aggregator behavior (F2.16.2) live in
dedicated suites and are not duplicated here. This suite focuses on:

  - auth gate: anonymous → 401.
  - HTTP wiring: route resolves, dependencies fire, response model
    serializes the service output.
  - Query-param validation: invalid UUID/datetime/enum return 422.
  - RBAC / tenancy at the HTTP boundary (driver, cross-store,
    unknown store, inactive store).
  - Source coverage end-to-end so the wire response carries
    inventory + order + compliance events.
  - Filters and pagination via query params.
  - Sort order (created_at DESC) observed in the wire response.
  - Compliance join behavior preserved through the API (no leak,
    no duplicate).
  - Existing audit/log routes are still resolvable after the new
    router landed.

Style mirrors tests/test_users_api.py and tests/test_audit_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Any
from typing import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.core.security import hash_password
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole


AUDIT_URL = "/stores/{store_id}/audit"
AUDIT_LIST_KEYS = {"items", "total", "limit", "offset"}
AUDIT_ITEM_KEYS = {
    "id",
    "source",
    "store_id",
    "actor_id",
    "action",
    "entity_type",
    "entity_id",
    "summary",
    "metadata",
    "created_at",
}


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *, name: str = "Audit-API", is_active: bool = True
    ) -> Store:
        store = Store(
            name=name,
            code=f"aapi-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _create(
        *,
        role: UserRole,
        store_id: UUID | None = None,
        is_active: bool = True,
    ) -> User:
        user = User(
            full_name=f"API {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            password_hash=hash_password("irrelevant-pw-1234"),
            role=role,
            store_id=store_id,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create() -> Product:
        product = Product(
            name=f"P-{uuid.uuid4().hex[:6]}",
            category="vape",
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
    def _create(*, product: Product) -> ProductVariant:
        variant = ProductVariant(
            product_id=product.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_item(db_session: Session) -> Callable[..., InventoryItem]:
    def _create(
        *, store: Store, variant: ProductVariant
    ) -> InventoryItem:
        item = InventoryItem(
            store_id=store.id,
            variant_id=variant.id,
            quantity_on_hand=10,
            quantity_reserved=0,
            reorder_threshold=0,
            status=InventoryStatus.available,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


@pytest.fixture
def make_order(db_session: Session) -> Callable[..., Order]:
    def _create(*, store: Store) -> Order:
        order = Order(
            store_id=store.id,
            idempotency_key=f"idem-{uuid.uuid4().hex[:8]}",
            status=OrderStatus.pending,
            subtotal_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order

    return _create


def _pin_created_at(
    db_session: Session, row: Any, when: datetime
) -> None:
    row.created_at = when
    db_session.commit()
    db_session.refresh(row)


@pytest.fixture
def make_inventory_log(
    db_session: Session,
) -> Callable[..., InventoryLog]:
    def _create(
        *,
        item: InventoryItem,
        movement_type: InventoryMovementType = (
            InventoryMovementType.receipt
        ),
        quantity_delta: int = 5,
        quantity_after: int = 15,
        actor: User | None = None,
        reason: str | None = None,
        created_at: datetime | None = None,
    ) -> InventoryLog:
        log = InventoryLog(
            inventory_item_id=item.id,
            store_id=item.store_id,
            variant_id=item.variant_id,
            performed_by_user_id=actor.id if actor is not None else None,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            quantity_after=quantity_after,
            reason=reason,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            _pin_created_at(db_session, log, created_at)
        return log

    return _create


@pytest.fixture
def make_order_audit_log(
    db_session: Session,
) -> Callable[..., OrderAuditLog]:
    def _create(
        *,
        order: Order,
        action: str = "status_changed",
        previous_status: OrderStatus | None = OrderStatus.pending,
        new_status: OrderStatus = OrderStatus.accepted,
        actor: User | None = None,
        reason: str | None = None,
        created_at: datetime | None = None,
    ) -> OrderAuditLog:
        log = OrderAuditLog(
            order_id=order.id,
            store_id=order.store_id,
            performed_by_user_id=actor.id if actor is not None else None,
            previous_status=previous_status,
            new_status=new_status,
            action=action,
            reason=reason,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            _pin_created_at(db_session, log, created_at)
        return log

    return _create


@pytest.fixture
def make_compliance_audit_log(
    db_session: Session,
) -> Callable[..., ProductComplianceAuditLog]:
    def _create(
        *,
        product: Product,
        actor: User | None = None,
        reason: str = "policy update",
        created_at: datetime | None = None,
    ) -> ProductComplianceAuditLog:
        log = ProductComplianceAuditLog(
            product_id=product.id,
            previous_compliance_status=ComplianceStatus.allowed,
            new_compliance_status=ComplianceStatus.restricted,
            previous_allowed_for_sale=True,
            new_allowed_for_sale=False,
            reason=reason,
            changed_by_user_id=actor.id if actor is not None else None,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            _pin_created_at(db_session, log, created_at)
        return log

    return _create


# --------------------------------------------------------------------- #
# A. Auth gate / query-param validation
# --------------------------------------------------------------------- #


class TestAuthGate:
    def test_anonymous_returns_401(
        self, client: TestClient, make_store
    ):
        store = make_store()
        resp = client.get(AUDIT_URL.format(store_id=store.id))
        assert resp.status_code == 401

    def test_authenticated_reaches_endpoint(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp.status_code == 200, resp.text


class TestQueryParamValidation:
    def test_invalid_uuid_in_path_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            "/stores/not-a-uuid/audit", headers=_auth(admin)
        )
        assert resp.status_code == 422

    def test_invalid_source_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"source": "user_audit"},
        )
        assert resp.status_code == 422

    def test_invalid_entity_type_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"entity_type": "user"},
        )
        assert resp.status_code == 422

    def test_invalid_actor_id_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"actor_id": "not-a-uuid"},
        )
        assert resp.status_code == 422

    def test_invalid_date_from_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"date_from": "not-a-date"},
        )
        assert resp.status_code == 422

    def test_invalid_date_to_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"date_to": "not-a-date"},
        )
        assert resp.status_code == 422


# --------------------------------------------------------------------- #
# B. Happy path / envelope
# --------------------------------------------------------------------- #


class TestEnvelope:
    def test_admin_gets_envelope_with_default_pagination(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == AUDIT_LIST_KEYS
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert body["total"] == 0
        assert body["items"] == []

    @pytest.mark.parametrize(
        "role", [UserRole.owner, UserRole.manager, UserRole.staff]
    )
    def test_non_admin_gets_envelope_for_own_store(
        self, client: TestClient, make_store, make_user, role
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(actor)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == AUDIT_LIST_KEYS

    def test_item_shape_and_serialization(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        make_inventory_log(item=item, actor=admin)

        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        event = body["items"][0]
        assert set(event.keys()) == AUDIT_ITEM_KEYS
        # Enums serialize as bare strings.
        assert event["source"] == "inventory"
        assert event["entity_type"] == "inventory_item"
        # UUID/datetime serialize as strings.
        assert isinstance(event["id"], str)
        UUID(event["id"])
        assert isinstance(event["store_id"], str)
        assert event["store_id"] == str(store.id)
        assert isinstance(event["created_at"], str)
        # Metadata is a dict.
        assert isinstance(event["metadata"], dict)


# --------------------------------------------------------------------- #
# C. RBAC / tenancy
# --------------------------------------------------------------------- #


class TestRBAC:
    def test_driver_returns_403(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(role=UserRole.driver, store_id=store.id)
        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(driver)
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "role", [UserRole.owner, UserRole.manager, UserRole.staff]
    )
    def test_non_admin_cross_store_returns_403(
        self, client: TestClient, make_store, make_user, role
    ):
        store_a = make_store()
        store_b = make_store()
        actor = make_user(role=role, store_id=store_a.id)
        resp = client.get(
            AUDIT_URL.format(store_id=store_b.id), headers=_auth(actor)
        )
        assert resp.status_code == 403

    def test_non_admin_unknown_store_returns_403(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store_id=store.id)
        unknown = uuid.uuid4()
        resp = client.get(
            AUDIT_URL.format(store_id=unknown), headers=_auth(owner)
        )
        # Anti-probe: cross-store and unknown collapse to 403.
        assert resp.status_code == 403

    def test_admin_unknown_store_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            AUDIT_URL.format(store_id=uuid.uuid4()),
            headers=_auth(admin),
        )
        assert resp.status_code == 404

    def test_admin_inactive_store_returns_400(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(is_active=False)
        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp.status_code == 400

    def test_non_admin_inactive_own_store_returns_400(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store(is_active=False)
        owner = make_user(role=UserRole.owner, store_id=store.id)
        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(owner)
        )
        assert resp.status_code == 400

    def test_admin_can_access_other_store(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item_b = make_item(store=store_b, variant=variant)
        make_inventory_log(item=item_b, actor=admin)

        resp_b = client.get(
            AUDIT_URL.format(store_id=store_b.id), headers=_auth(admin)
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["total"] == 1


# --------------------------------------------------------------------- #
# D. Source coverage end-to-end
# --------------------------------------------------------------------- #


class TestSourceCoverage:
    def test_all_three_sources_appear_in_feed(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)

        make_inventory_log(item=item, actor=admin)
        make_order_audit_log(order=order, actor=admin)
        make_compliance_audit_log(product=product, actor=admin)

        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        seen = {(it["source"], it["entity_type"]) for it in body["items"]}
        assert ("inventory", "inventory_item") in seen
        assert ("order", "order") in seen
        assert ("product_compliance", "product") in seen

    def test_compliance_does_not_leak_to_store_without_inventory(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product = make_product()
        variant = make_variant(product=product)
        # Only store_a carries inventory for the product.
        make_item(store=store_a, variant=variant)
        make_compliance_audit_log(product=product, actor=admin)

        resp_b = client.get(
            AUDIT_URL.format(store_id=store_b.id), headers=_auth(admin)
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["total"] == 0

        resp_a = client.get(
            AUDIT_URL.format(store_id=store_a.id), headers=_auth(admin)
        )
        assert resp_a.json()["total"] == 1

    def test_compliance_not_duplicated_with_multiple_variants(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant_a = make_variant(product=product)
        variant_b = make_variant(product=product)
        make_item(store=store, variant=variant_a)
        make_item(store=store, variant=variant_b)
        make_compliance_audit_log(product=product, actor=admin)

        resp = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp.json()["total"] == 1


# --------------------------------------------------------------------- #
# E. Filters
# --------------------------------------------------------------------- #


@pytest.fixture
def seeded_feed(
    db_session,
    make_store,
    make_user,
    make_product,
    make_variant,
    make_item,
    make_order,
    make_inventory_log,
    make_order_audit_log,
    make_compliance_audit_log,
):
    """One row per source, distinct actors and timestamps so every
    filter has a positive and negative target."""
    store = make_store()
    admin = make_user(role=UserRole.admin)
    inv_actor = make_user(role=UserRole.manager, store_id=store.id)
    ord_actor = make_user(role=UserRole.staff, store_id=store.id)
    product = make_product()
    variant = make_variant(product=product)
    item = make_item(store=store, variant=variant)
    order = make_order(store=store)

    t_inv = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)
    t_ord = datetime(2026, 1, 2, 8, 0, 0, tzinfo=UTC)
    t_comp = datetime(2026, 1, 3, 8, 0, 0, tzinfo=UTC)

    inv = make_inventory_log(
        item=item,
        movement_type=InventoryMovementType.adjustment,
        quantity_delta=-2,
        actor=inv_actor,
        reason="loss",
        created_at=t_inv,
    )
    ordr = make_order_audit_log(
        order=order,
        action="order_canceled",
        previous_status=OrderStatus.pending,
        new_status=OrderStatus.canceled,
        actor=ord_actor,
        reason="customer",
        created_at=t_ord,
    )
    comp = make_compliance_audit_log(
        product=product, actor=admin, created_at=t_comp
    )

    return {
        "store": store,
        "admin": admin,
        "inv_actor": inv_actor,
        "ord_actor": ord_actor,
        "inv": inv,
        "ordr": ordr,
        "comp": comp,
    }


class TestFilters:
    @pytest.mark.parametrize(
        "source_value,expected_id_key",
        [
            ("inventory", "inv"),
            ("order", "ordr"),
            ("product_compliance", "comp"),
        ],
    )
    def test_source_filter(
        self,
        client: TestClient,
        seeded_feed,
        source_value,
        expected_id_key,
    ):
        store = seeded_feed["store"]
        admin = seeded_feed["admin"]
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"source": source_value},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["source"] == source_value
        assert body["items"][0]["id"] == str(seeded_feed[expected_id_key].id)

    @pytest.mark.parametrize(
        "entity_value,expected_id_key",
        [
            ("inventory_item", "inv"),
            ("order", "ordr"),
            ("product", "comp"),
        ],
    )
    def test_entity_type_filter(
        self,
        client: TestClient,
        seeded_feed,
        entity_value,
        expected_id_key,
    ):
        store = seeded_feed["store"]
        admin = seeded_feed["admin"]
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"entity_type": entity_value},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["entity_type"] == entity_value
        assert body["items"][0]["id"] == str(seeded_feed[expected_id_key].id)

    def test_action_filter_inventory(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"action": "adjustment"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(seeded_feed["inv"].id)

    def test_action_filter_order(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"action": "order_canceled"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(seeded_feed["ordr"].id)

    def test_action_filter_compliance_changed(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"action": "compliance_changed"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(seeded_feed["comp"].id)

    def test_action_filter_nonmatching_returns_empty(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"action": "no_such_action"},
        )
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_actor_id_filter(self, client: TestClient, seeded_feed):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"actor_id": str(seeded_feed["inv_actor"].id)},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(seeded_feed["inv"].id)

    def test_date_from_filters_older_rows_out(
        self, client: TestClient, seeded_feed
    ):
        # Cut between t_inv (Jan 1) and t_ord (Jan 2).
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"date_from": "2026-01-02T00:00:00+00:00"},
        )
        body = resp.json()
        assert body["total"] == 2
        ids = {it["id"] for it in body["items"]}
        assert str(seeded_feed["inv"].id) not in ids
        assert str(seeded_feed["ordr"].id) in ids
        assert str(seeded_feed["comp"].id) in ids

    def test_date_to_filters_newer_rows_out(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"date_to": "2026-01-02T23:59:59+00:00"},
        )
        body = resp.json()
        assert body["total"] == 2
        ids = {it["id"] for it in body["items"]}
        assert str(seeded_feed["comp"].id) not in ids
        assert str(seeded_feed["inv"].id) in ids
        assert str(seeded_feed["ordr"].id) in ids


# --------------------------------------------------------------------- #
# F. Pagination + sorting
# --------------------------------------------------------------------- #


class TestPagination:
    def test_limit_1_returns_one_item(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"limit": 1},
        )
        body = resp.json()
        assert body["limit"] == 1
        assert len(body["items"]) == 1
        # total preserves the full pre-pagination count.
        assert body["total"] == 3

    def test_limit_200_accepted(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"limit": 200},
        )
        assert resp.status_code == 200
        assert resp.json()["limit"] == 200

    def test_limit_0_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"limit": 0},
        )
        assert resp.status_code == 422

    def test_limit_over_200_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"limit": 201},
        )
        assert resp.status_code == 422

    def test_offset_negative_returns_422(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        resp = client.get(
            AUDIT_URL.format(store_id=store.id),
            headers=_auth(admin),
            params={"offset": -1},
        )
        assert resp.status_code == 422

    def test_offset_beyond_total_returns_empty_items(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"offset": 99},
        )
        body = resp.json()
        assert body["total"] == 3
        assert body["items"] == []
        assert body["offset"] == 99


class TestSorting:
    def test_created_at_desc_ordering_via_api(
        self, client: TestClient, seeded_feed
    ):
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
        )
        body = resp.json()
        # Seeded timestamps: comp (Jan 3) > ordr (Jan 2) > inv (Jan 1).
        # DESC: comp, ordr, inv.
        ids_in_order = [it["id"] for it in body["items"]]
        assert ids_in_order == [
            str(seeded_feed["comp"].id),
            str(seeded_feed["ordr"].id),
            str(seeded_feed["inv"].id),
        ]

    def test_offset_limit_applied_after_global_merge(
        self, client: TestClient, seeded_feed
    ):
        # offset=1, limit=1 over the 3-row DESC feed must skip comp
        # and return ordr.
        resp = client.get(
            AUDIT_URL.format(store_id=seeded_feed["store"].id),
            headers=_auth(seeded_feed["admin"]),
            params={"offset": 1, "limit": 1},
        )
        body = resp.json()
        assert body["total"] == 3
        assert body["offset"] == 1
        assert body["limit"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["id"] == str(seeded_feed["ordr"].id)


# --------------------------------------------------------------------- #
# G. Existing route regression (smoke at API level)
# --------------------------------------------------------------------- #


class TestExistingRouteRegression:
    """The new audit router must not have shadowed or broken the
    pre-existing audit/log endpoints under `/stores`, `/inventory`,
    `/orders` and `/products`. A 404 here would indicate a route
    registration conflict; the auth gate (401) confirms the path
    resolved and went through the dependency stack.
    """

    def test_store_inventory_logs_route_still_resolves(
        self, client: TestClient
    ):
        resp = client.get(f"/stores/{uuid.uuid4()}/inventory/logs")
        # Unauthenticated → 401 (proves route resolves).
        assert resp.status_code == 401

    def test_order_audit_logs_route_still_resolves(
        self, client: TestClient
    ):
        resp = client.get(f"/orders/{uuid.uuid4()}/audit-logs")
        assert resp.status_code == 401

    def test_product_compliance_audit_route_still_resolves(
        self, client: TestClient
    ):
        resp = client.get(f"/products/{uuid.uuid4()}/compliance-audit")
        assert resp.status_code == 401

    def test_new_audit_endpoint_not_shadowing_store_get(
        self, client: TestClient, make_store, make_user
    ):
        """Sanity: GET /stores/{id} (store profile) and GET
        /stores/{id}/audit (new feed) must coexist."""
        admin = make_user(role=UserRole.admin)
        store = make_store()
        # GET /stores/{id} (existing).
        resp_profile = client.get(
            f"/stores/{store.id}", headers=_auth(admin)
        )
        assert resp_profile.status_code == 200
        # GET /stores/{id}/audit (new).
        resp_audit = client.get(
            AUDIT_URL.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp_audit.status_code == 200
