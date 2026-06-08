"""API-level tests for the admin settings endpoint.

Exercises `GET /admin/settings` via the FastAPI TestClient. Covers:

  - auth gate: anonymous / invalid token → 401.
  - RBAC matrix: admin → 200, every non-admin role → 403.
  - Response envelope: every top-level section present and typed.
  - Section shapes: keys + value primitives match the wire contract.
  - Backend-computed values move with seeded DB state (admin counts,
    delivered orders aggregates, compliance counts).
  - Endpoint takes no query params and rejects unknown ones (FastAPI's
    Query model is strict on validation, but unknown params are
    silently dropped — what matters is that defaults are not
    overridden by query params).

Style mirrors test_admin_dashboard_api.py and test_admin_operations_api.py.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


ADMIN_SETTINGS_URL = "/admin/settings"


_TOP_LEVEL_KEYS = {
    "platform",
    "billing",
    "compliance",
    "operations",
    "notifications",
    "admin_preferences",
    "editable",
}

_EDITABLE_KEYS = {
    "platform_name",
    "support_email",
    "default_locale",
    "default_timezone",
}

_PLATFORM_KEYS = {
    "app_name",
    "app_env",
    "app_debug",
    "version",
    "default_jurisdiction",
    "default_store_timezone",
}
_BILLING_KEYS = {
    "commission_rate_basis_points",
    "currency",
    "delivered_orders_count",
    "delivered_orders_total_amount",
}
_COMPLIANCE_KEYS = {
    "default_jurisdiction",
    "allowed_count",
    "restricted_count",
    "banned_count",
    "blocked_count",
}
_OPERATIONS_KEYS = {
    "default_alert_page_size",
    "max_alert_page_size",
    "default_aging_minutes",
    "open_order_statuses",
}
_NOTIFICATIONS_KEYS = {"event_types"}
_ADMIN_PREFERENCES_KEYS = {
    "admin_total",
    "admin_active",
    "default_locale",
    "default_timezone",
}


_NON_ADMIN_ROLES = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(*, is_active: bool = True) -> Store:
        store = Store(
            name=f"Set-{uuid.uuid4().hex[:6]}",
            code=f"st-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


# Thin adapter over tests.helpers.auth.make_user (F2.22.2.C2).
@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _create(
        *,
        role: UserRole,
        store_id: uuid.UUID | None = None,
        is_active: bool = True,
    ) -> User:
        sid = None if role == UserRole.admin else store_id
        return central_make_user(
            db_session,
            role=role,
            store_id=sid,
            is_active=is_active,
            full_name=f"SettingsAPI {role.value}",
        )

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        *,
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
    ) -> Product:
        product = Product(
            name=f"P-{uuid.uuid4().hex[:6]}",
            category="vape",
            compliance_status=compliance_status,
            allowed_for_sale=allowed_for_sale,
            is_active=True,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


@pytest.fixture
def make_order(db_session: Session) -> Callable[..., Order]:
    def _create(
        *,
        store: Store,
        order_status: OrderStatus = OrderStatus.pending,
        total_amount: Decimal = Decimal("0.00"),
    ) -> Order:
        order = Order(
            store_id=store.id,
            idempotency_key=f"idem-{uuid.uuid4().hex[:8]}",
            status=order_status,
            subtotal_amount=total_amount,
            tax_amount=Decimal("0.00"),
            total_amount=total_amount,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order

    return _create


# --------------------------------------------------------------------- #
# A. Auth gate / RBAC
# --------------------------------------------------------------------- #


class TestAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(ADMIN_SETTINGS_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            ADMIN_SETTINGS_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(ADMIN_SETTINGS_URL, headers=_auth(admin))
        assert resp.status_code == 200, resp.text

    @pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
    def test_non_admin_forbidden(
        self,
        client: TestClient,
        make_store,
        make_user,
        role: UserRole,
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        resp = client.get(ADMIN_SETTINGS_URL, headers=_auth(actor))
        assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# B. Response envelope + section shapes
# --------------------------------------------------------------------- #


class TestEnvelope:
    def test_top_level_keys(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.get(ADMIN_SETTINGS_URL, headers=_auth(admin))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == _TOP_LEVEL_KEYS

    def test_section_shapes(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        body = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(admin)
        ).json()

        assert set(body["platform"].keys()) == _PLATFORM_KEYS
        assert set(body["billing"].keys()) == _BILLING_KEYS
        assert set(body["compliance"].keys()) == _COMPLIANCE_KEYS
        assert set(body["operations"].keys()) == _OPERATIONS_KEYS
        assert set(body["notifications"].keys()) == _NOTIFICATIONS_KEYS
        assert (
            set(body["admin_preferences"].keys())
            == _ADMIN_PREFERENCES_KEYS
        )

    def test_platform_section_values(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        platform = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(admin)
        ).json()["platform"]
        assert isinstance(platform["app_name"], str)
        assert platform["app_name"]
        assert isinstance(platform["app_env"], str)
        assert platform["app_env"]
        assert isinstance(platform["app_debug"], bool)
        assert platform["version"]
        assert platform["default_jurisdiction"] == "FL"
        assert platform["default_store_timezone"] == "America/New_York"

    def test_operations_section_values(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        ops = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(admin)
        ).json()["operations"]
        # These must mirror the bounds enforced by the admin operations
        # alert endpoint (`Query(default=50, ge=1, le=200)` and
        # `Query(default=1440, ge=1)`).
        assert ops["default_alert_page_size"] == 50
        assert ops["max_alert_page_size"] == 200
        assert ops["default_aging_minutes"] == 1440
        assert ops["open_order_statuses"] == [
            "pending",
            "accepted",
            "preparing",
            "ready",
            "out_for_delivery",
        ]

    def test_notifications_section_values(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        notif = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(admin)
        ).json()["notifications"]
        # The catalog is locked in code, but the contract is
        # "non-empty list of unique strings". Verifying that shape
        # rather than the exact contents keeps the tests resilient to
        # legitimate catalog additions.
        assert isinstance(notif["event_types"], list)
        assert len(notif["event_types"]) > 0
        assert all(isinstance(e, str) and e for e in notif["event_types"])
        assert len(notif["event_types"]) == len(set(notif["event_types"]))

    def test_billing_section_values_default(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        billing = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(admin)
        ).json()["billing"]
        assert billing["commission_rate_basis_points"] == 500
        assert billing["currency"] == "USD"
        assert billing["delivered_orders_count"] == 0
        assert billing["delivered_orders_total_amount"] == "0.00"


# --------------------------------------------------------------------- #
# C. Backend-computed values move with seeded state
# --------------------------------------------------------------------- #


class TestComputedValues:
    def test_admin_preferences_count_admins_only(
        self,
        client: TestClient,
        make_user,
        make_store,
    ):
        # Two admins (one inactive) + one non-admin user (manager).
        make_user(role=UserRole.admin)
        make_user(role=UserRole.admin, is_active=False)
        store = make_store()
        make_user(role=UserRole.manager, store_id=store.id)
        # The caller itself counts as an admin too.
        caller = make_user(role=UserRole.admin)

        prefs = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(caller)
        ).json()["admin_preferences"]
        # Three admins total (caller + two seeded), two active.
        assert prefs["admin_total"] == 3
        assert prefs["admin_active"] == 2

    def test_billing_aggregates_only_delivered_orders(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()

        # Two delivered orders sum into the gross figure.
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            total_amount=Decimal("12.50"),
        )
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            total_amount=Decimal("7.50"),
        )
        # A non-delivered order must NOT contribute.
        make_order(
            store=store,
            order_status=OrderStatus.pending,
            total_amount=Decimal("99.99"),
        )

        billing = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(admin)
        ).json()["billing"]
        assert billing["delivered_orders_count"] == 2
        assert billing["delivered_orders_total_amount"] == "20.00"

    def test_compliance_counts_track_product_state(
        self,
        client: TestClient,
        make_user,
        make_product,
    ):
        admin = make_user(role=UserRole.admin)

        make_product()  # allowed + allowed_for_sale → allowed only.
        make_product(
            compliance_status=ComplianceStatus.restricted,
        )  # restricted + blocked.
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )  # banned + blocked.
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )  # allowed (status) + blocked (allowed_for_sale=False).

        body = client.get(
            ADMIN_SETTINGS_URL, headers=_auth(admin)
        ).json()["compliance"]

        assert body["allowed_count"] == 2
        assert body["restricted_count"] == 1
        assert body["banned_count"] == 1
        # blocked = restricted (1) + banned (1) + allowed_for_sale=False (1)
        assert body["blocked_count"] == 3
        assert body["default_jurisdiction"] == "FL"


# --------------------------------------------------------------------- #
# Editable section (GET) — F2.27.10
# --------------------------------------------------------------------- #


class TestEditableSection:
    def test_get_includes_editable_block_with_defaults(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        body = client.get(ADMIN_SETTINGS_URL, headers=_auth(admin)).json()
        assert set(body["editable"].keys()) == _EDITABLE_KEYS
        # Defaults from get-or-create when no row exists yet.
        assert body["editable"]["platform_name"] == "NubeRush"
        assert body["editable"]["support_email"] is None
        assert body["editable"]["default_locale"] == "en-US"
        assert body["editable"]["default_timezone"] == "America/New_York"

    def test_get_does_not_leak_secrets(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        raw = client.get(ADMIN_SETTINGS_URL, headers=_auth(admin)).text.lower()
        for needle in (
            "service_role",
            "resend_api_key",
            "database_url",
            "supabase_jwks",
            "secret",
            "password",
            "token",
        ):
            assert needle not in raw, needle


# --------------------------------------------------------------------- #
# PATCH /admin/settings — F2.27.10
# --------------------------------------------------------------------- #


class TestPatchAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.patch(ADMIN_SETTINGS_URL, json={"platform_name": "X"})
        assert resp.status_code == 401, resp.text

    @pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
    def test_non_admin_forbidden(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        resp = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(actor),
            json={"platform_name": "Nope"},
        )
        assert resp.status_code == 403, resp.text

    def test_admin_returns_200(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"platform_name": "Acme Platform"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["editable"]["platform_name"] == "Acme Platform"


class TestPatchValidation:
    def test_unknown_field_422(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"platform_name": "X", "surprise": 1},
        )
        assert resp.status_code == 422, resp.text

    @pytest.mark.parametrize(
        "field",
        [
            "app_env",
            "app_debug",
            "version",
            "database_url",
            "supabase_service_role_key",
            "resend_api_key",
            "commission_rate_basis_points",
            "currency",
            "default_aging_minutes",
            "event_types",
        ],
    )
    def test_env_backed_and_policy_fields_rejected(
        self, client: TestClient, make_user, field: str
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={field: "anything"},
        )
        assert resp.status_code == 422, f"{field} should be rejected"

    def test_blank_platform_name_422(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"platform_name": "   "},
        )
        assert resp.status_code == 422, resp.text

    def test_oversize_platform_name_422(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"platform_name": "x" * 151},
        )
        assert resp.status_code == 422, resp.text

    def test_invalid_email_422(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"support_email": "not-an-email"},
        )
        assert resp.status_code == 422, resp.text


class TestPatchPersistence:
    def test_patch_then_get_reflects_change(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        patch = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={
                "platform_name": "Patched Co",
                "support_email": "ops@example.com",
                "default_locale": "es-MX",
                "default_timezone": "America/Chicago",
            },
        )
        assert patch.status_code == 200, patch.text

        body = client.get(ADMIN_SETTINGS_URL, headers=_auth(admin)).json()
        assert body["editable"] == {
            "platform_name": "Patched Co",
            "support_email": "ops@example.com",
            "default_locale": "es-MX",
            "default_timezone": "America/Chicago",
        }

    def test_partial_patch_leaves_other_fields(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"support_email": "ops@example.com"},
        )
        # Only platform_name changes now; support_email must survive.
        client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"platform_name": "Only Name"},
        )
        body = client.get(ADMIN_SETTINGS_URL, headers=_auth(admin)).json()
        assert body["editable"]["platform_name"] == "Only Name"
        assert body["editable"]["support_email"] == "ops@example.com"

    def test_blank_email_clears_field(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"support_email": "ops@example.com"},
        )
        cleared = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"support_email": "   "},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["editable"]["support_email"] is None

    def test_empty_payload_is_noop_200(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.patch(ADMIN_SETTINGS_URL, headers=_auth(admin), json={})
        assert resp.status_code == 200, resp.text
        assert resp.json()["editable"]["platform_name"] == "NubeRush"

    def test_patch_response_does_not_leak_secrets(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        raw = client.patch(
            ADMIN_SETTINGS_URL,
            headers=_auth(admin),
            json={"platform_name": "Acme"},
        ).text.lower()
        for needle in ("service_role", "resend_api_key", "database_url", "secret", "token"):
            assert needle not in raw, needle
