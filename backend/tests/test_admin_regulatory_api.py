"""API-level tests for the admin Regulatory Intelligence routes (F2.26.5.E).

Exercises `/admin/regulatory/*` via the FastAPI TestClient:
  - the admin-only RBAC gate (admin → 2xx; non-admin → 403; anon → 401);
  - sources (list/create + validation), notices (list/ingest + dedupe),
    detect-matches, create-alerts, alert list/detail/filters, and the
    acknowledge/dismiss/resolve lifecycle;
  - API-level side-effect safety: ingest never auto-matches, detect-matches
    never auto-creates alerts, create-alerts never auto-resolves, and
    hold/ban resolution produces the existing product compliance audit log +
    inventory quarantine cascade (no direct Product/Inventory write in route).

Style mirrors tests/test_admin_compliance_api.py.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryStatus
from app.db.models import OperationalAuditLog
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services import regulatory_ingestion as _ingestion_svc
from app.services.regulatory_sources import StaticRegulatorySourceClient
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


BASE = "/admin/regulatory"


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def admin(db_session: Session) -> User:
    return central_make_user(db_session, role=UserRole.admin)


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(*, name: str = "Example Vape") -> Product:
        product = Product(
            name=name, brand=None, category="ENDS",
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True, is_active=True,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


def _make_source(client: TestClient, admin: User, **over) -> dict:
    body = {"name": f"S {uuid.uuid4().hex[:8]}", "kind": "manual"}
    body.update(over)
    resp = client.post(f"{BASE}/sources", headers=_auth(admin), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _ingest_notice(client: TestClient, admin: User, source_id, payload) -> dict:
    body = {
        "source_id": source_id,
        "title": "t",
        "notice_type": "manual_snapshot",
        "payload": payload,
    }
    resp = client.post(f"{BASE}/notices", headers=_auth(admin), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _open_alert_id(
    client: TestClient, admin: User, db_session: Session, make_product,
    *, name: str = "Example Vape",
) -> tuple[dict, str]:
    """Create product + name-matched notice, run detect + create-alerts; return
    (product_dict-ish, alert_id) with one open high/hold alert."""
    product = make_product(name=name)
    source = _make_source(client, admin)
    notice = _ingest_notice(
        client, admin, source["id"], {"product_name": name}
    )
    r1 = client.post(
        f"{BASE}/notices/{notice['id']}/detect-matches", headers=_auth(admin)
    )
    assert r1.status_code == 200, r1.text
    assert len(r1.json()) == 1
    r2 = client.post(
        f"{BASE}/notices/{notice['id']}/create-alerts", headers=_auth(admin)
    )
    assert r2.status_code == 200, r2.text
    alerts = r2.json()
    assert len(alerts) == 1
    return product, alerts[0]["id"]


# ===================================================================== #
# RBAC gate
# ===================================================================== #


_NON_ADMIN_ROLES = [
    UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver,
]


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_non_admin_forbidden_on_list_and_create(
    client: TestClient, db_session: Session, role: UserRole
):
    user = central_make_user(db_session, role=role, store_id=None)
    assert client.get(f"{BASE}/sources", headers=_auth(user)).status_code == 403
    assert client.get(f"{BASE}/alerts", headers=_auth(user)).status_code == 403
    assert client.post(
        f"{BASE}/sources", headers=_auth(user),
        json={"name": "x", "kind": "manual"},
    ).status_code == 403


def test_anonymous_unauthorized(client: TestClient):
    assert client.get(f"{BASE}/sources").status_code == 401
    assert client.get(f"{BASE}/alerts").status_code == 401


def test_non_admin_forbidden_on_lifecycle(
    client: TestClient, db_session: Session, admin: User, make_product
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    staff = central_make_user(db_session, role=UserRole.staff, store_id=None)
    for verb in ("acknowledge", "dismiss", "resolve"):
        body = (
            {"action": "no_action", "resolution_note": "x"}
            if verb == "resolve"
            else {"reason": "x"}
        )
        resp = client.post(
            f"{BASE}/alerts/{alert_id}/{verb}", headers=_auth(staff), json=body
        )
        assert resp.status_code == 403


# ===================================================================== #
# Sources
# ===================================================================== #


def test_create_and_list_sources(client: TestClient, admin: User):
    created = _make_source(client, admin, name="FDA PMTA Feed")
    assert created["is_active"] is True

    resp = client.get(f"{BASE}/sources", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert any(s["id"] == created["id"] for s in body["items"])


def test_create_source_duplicate_name_422(client: TestClient, admin: User):
    _make_source(client, admin, name="Dupe Feed")
    resp = client.post(
        f"{BASE}/sources", headers=_auth(admin),
        json={"name": "Dupe Feed", "kind": "manual"},
    )
    assert resp.status_code == 422


def test_create_source_invalid_payload_422(client: TestClient, admin: User):
    # blank name
    assert client.post(
        f"{BASE}/sources", headers=_auth(admin),
        json={"name": "  ", "kind": "manual"},
    ).status_code == 422
    # bad kind
    assert client.post(
        f"{BASE}/sources", headers=_auth(admin),
        json={"name": "x", "kind": "not_a_kind"},
    ).status_code == 422
    # extra field
    assert client.post(
        f"{BASE}/sources", headers=_auth(admin),
        json={"name": "x", "kind": "manual", "surprise": 1},
    ).status_code == 422


def test_sources_pagination_and_is_active_filter(
    client: TestClient, admin: User
):
    active = _make_source(client, admin)
    inactive = _make_source(client, admin, is_active=False)

    resp = client.get(
        f"{BASE}/sources", headers=_auth(admin), params={"is_active": "true"}
    )
    ids = {s["id"] for s in resp.json()["items"]}
    assert active["id"] in ids
    assert inactive["id"] not in ids

    resp2 = client.get(
        f"{BASE}/sources", headers=_auth(admin),
        params={"limit": 1, "offset": 0},
    )
    assert resp2.json()["limit"] == 1
    assert len(resp2.json()["items"]) == 1

    # invalid pagination -> 422 at the query-param layer.
    assert client.get(
        f"{BASE}/sources", headers=_auth(admin), params={"limit": 0}
    ).status_code == 422


# ===================================================================== #
# Notices
# ===================================================================== #


def test_ingest_and_list_notices(client: TestClient, admin: User):
    source = _make_source(client, admin)
    notice = _ingest_notice(client, admin, source["id"], {"k": "v"})
    assert notice["content_hash"]

    resp = client.get(f"{BASE}/notices", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(n["id"] == notice["id"] for n in resp.json()["items"])


def test_ingest_notice_dedupe_reuses(client: TestClient, admin: User):
    source = _make_source(client, admin)
    first = _ingest_notice(client, admin, source["id"], {"k": "v"})
    second = _ingest_notice(client, admin, source["id"], {"k": "v"})
    assert first["id"] == second["id"]


def test_ingest_notice_invalid_source_404(client: TestClient, admin: User):
    resp = client.post(
        f"{BASE}/notices", headers=_auth(admin),
        json={
            "source_id": str(uuid.uuid4()),
            "title": "t",
            "notice_type": "manual_snapshot",
            "payload": {},
        },
    )
    assert resp.status_code == 404


def test_ingest_notice_invalid_payload_422(client: TestClient, admin: User):
    source = _make_source(client, admin)
    # blank title
    assert client.post(
        f"{BASE}/notices", headers=_auth(admin),
        json={
            "source_id": source["id"], "title": "  ",
            "notice_type": "manual_snapshot", "payload": {},
        },
    ).status_code == 422
    # bad notice_type
    assert client.post(
        f"{BASE}/notices", headers=_auth(admin),
        json={
            "source_id": source["id"], "title": "t",
            "notice_type": "bogus", "payload": {},
        },
    ).status_code == 422


def test_notices_filters(client: TestClient, admin: User):
    source_a = _make_source(client, admin)
    source_b = _make_source(client, admin)
    n_a = _ingest_notice(client, admin, source_a["id"], {"x": 1})
    _ingest_notice(client, admin, source_b["id"], {"x": 2})

    resp = client.get(
        f"{BASE}/notices", headers=_auth(admin),
        params={"source_id": source_a["id"]},
    )
    ids = {n["id"] for n in resp.json()["items"]}
    assert ids == {n_a["id"]}

    resp2 = client.get(
        f"{BASE}/notices", headers=_auth(admin),
        params={"notice_type": "manual_snapshot"},
    )
    assert all(n["notice_type"] == "manual_snapshot" for n in resp2.json()["items"])


# ===================================================================== #
# detect-matches
# ===================================================================== #


def test_detect_matches_idempotent_and_no_alerts(
    client: TestClient, db_session: Session, admin: User, make_product
):
    make_product(name="Example Vape")
    source = _make_source(client, admin)
    notice = _ingest_notice(
        client, admin, source["id"], {"product_name": "Example Vape"}
    )
    url = f"{BASE}/notices/{notice['id']}/detect-matches"

    first = client.post(url, headers=_auth(admin))
    second = client.post(url, headers=_auth(admin))
    assert first.status_code == 200
    assert len(first.json()) == 1
    assert {m["id"] for m in first.json()} == {m["id"] for m in second.json()}
    assert first.json()[0]["match_strategy"] == "name"

    # detect-matches must NOT auto-create alerts.
    alerts = client.get(f"{BASE}/alerts", headers=_auth(admin)).json()
    assert alerts["total"] == 0


def test_detect_matches_missing_notice_404(client: TestClient, admin: User):
    resp = client.post(
        f"{BASE}/notices/{uuid.uuid4()}/detect-matches", headers=_auth(admin)
    )
    assert resp.status_code == 404


def test_detect_matches_non_admin_403(
    client: TestClient, db_session: Session, admin: User, make_product
):
    make_product(name="Example Vape")
    source = _make_source(client, admin)
    notice = _ingest_notice(
        client, admin, source["id"], {"product_name": "Example Vape"}
    )
    user = central_make_user(db_session, role=UserRole.manager, store_id=None)
    resp = client.post(
        f"{BASE}/notices/{notice['id']}/detect-matches", headers=_auth(user)
    )
    assert resp.status_code == 403


# ===================================================================== #
# create-alerts
# ===================================================================== #


def test_create_alerts_idempotent_and_no_mutation(
    client: TestClient, db_session: Session, admin: User, make_product
):
    product = make_product(name="Example Vape")
    source = _make_source(client, admin)
    notice = _ingest_notice(
        client, admin, source["id"], {"product_name": "Example Vape"}
    )
    client.post(
        f"{BASE}/notices/{notice['id']}/detect-matches", headers=_auth(admin)
    )
    url = f"{BASE}/notices/{notice['id']}/create-alerts"
    first = client.post(url, headers=_auth(admin))
    second = client.post(url, headers=_auth(admin))
    assert first.status_code == 200
    assert len(first.json()) == 1
    assert first.json()[0]["status"] == "open"
    assert {a["id"] for a in first.json()} == {a["id"] for a in second.json()}

    # No product mutation, no compliance audit.
    db_session.refresh(product)
    assert product.compliance_status == ComplianceStatus.allowed
    assert product.allowed_for_sale is True
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


def test_create_alerts_missing_notice_404(client: TestClient, admin: User):
    resp = client.post(
        f"{BASE}/notices/{uuid.uuid4()}/create-alerts", headers=_auth(admin)
    )
    assert resp.status_code == 404


# ===================================================================== #
# Alerts list / detail
# ===================================================================== #


def test_alerts_list_detail_and_filters(
    client: TestClient, db_session: Session, admin: User, make_product
):
    product, alert_id = _open_alert_id(client, admin, db_session, make_product)

    # detail
    detail = client.get(f"{BASE}/alerts/{alert_id}", headers=_auth(admin))
    assert detail.status_code == 200
    assert detail.json()["id"] == alert_id
    assert detail.json()["severity"] == "high"
    assert detail.json()["recommended_action"] == "hold"

    # filters
    for params in (
        {"status": "open"},
        {"severity": "high"},
        {"recommended_action": "hold"},
        {"product_id": str(product.id)},
    ):
        resp = client.get(f"{BASE}/alerts", headers=_auth(admin), params=params)
        assert resp.status_code == 200
        assert any(a["id"] == alert_id for a in resp.json()["items"]), params

    # a non-matching filter excludes it
    resp = client.get(
        f"{BASE}/alerts", headers=_auth(admin), params={"status": "dismissed"}
    )
    assert all(a["id"] != alert_id for a in resp.json()["items"])


def test_get_alert_missing_404(client: TestClient, admin: User):
    resp = client.get(f"{BASE}/alerts/{uuid.uuid4()}", headers=_auth(admin))
    assert resp.status_code == 404


# ===================================================================== #
# Lifecycle endpoints
# ===================================================================== #


def test_acknowledge(client: TestClient, db_session, admin, make_product):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    resp = client.post(
        f"{BASE}/alerts/{alert_id}/acknowledge", headers=_auth(admin),
        json={"reason": "reviewing"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"
    # No compliance audit.
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


def test_dismiss(client: TestClient, db_session, admin, make_product):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    resp = client.post(
        f"{BASE}/alerts/{alert_id}/dismiss", headers=_auth(admin),
        json={"reason": "not ours"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"
    assert resp.json()["resolved_at"] is not None
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


def test_resolve_no_action(client: TestClient, db_session, admin, make_product):
    product, alert_id = _open_alert_id(client, admin, db_session, make_product)
    resp = client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "no_action", "resolution_note": "fine"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "actioned"
    db_session.refresh(product)
    assert product.compliance_status == ComplianceStatus.allowed
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


def test_resolve_hold_produces_compliance_audit(
    client: TestClient, db_session, admin, make_product
):
    product, alert_id = _open_alert_id(client, admin, db_session, make_product)
    resp = client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "hold", "resolution_note": "pending review"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "actioned"

    db_session.refresh(product)
    assert product.compliance_status == ComplianceStatus.restricted
    assert product.allowed_for_sale is False
    audit = db_session.scalar(
        select(ProductComplianceAuditLog).where(
            ProductComplianceAuditLog.product_id == product.id
        )
    )
    assert audit is not None
    assert str(alert_id) in audit.reason


def test_resolve_ban_cascades_inventory(
    client: TestClient, db_session, admin, make_product
):
    product, alert_id = _open_alert_id(client, admin, db_session, make_product)
    variant = ProductVariant(
        product_id=product.id, sku=f"sku-{uuid.uuid4().hex[:8]}",
        price=Decimal("5.00"),
    )
    db_session.add(variant)
    db_session.flush()
    store = Store(name="S", code=f"c-{uuid.uuid4().hex[:8]}")
    db_session.add(store)
    db_session.flush()
    item = InventoryItem(
        store_id=store.id, variant_id=variant.id,
        quantity_on_hand=10, status=InventoryStatus.available,
    )
    db_session.add(item)
    db_session.commit()
    item_id = item.id

    resp = client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "ban", "resolution_note": "FDA enforcement"},
    )
    assert resp.status_code == 200

    db_session.refresh(product)
    assert product.compliance_status == ComplianceStatus.banned
    assert product.allowed_for_sale is False
    # Existing ban -> quarantine cascade preserved.
    refreshed = db_session.get(InventoryItem, item_id)
    db_session.refresh(refreshed)
    assert refreshed.status == InventoryStatus.quarantined
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 1


def test_resolve_invalid_transition_422(
    client: TestClient, db_session, admin, make_product
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    # First resolution actions the alert.
    client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "no_action", "resolution_note": "ok"},
    )
    # Second resolve on a terminal alert -> 422.
    resp = client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "hold", "resolution_note": "again"},
    )
    assert resp.status_code == 422


def test_resolve_invalid_action_and_blank_note_422(
    client: TestClient, db_session, admin, make_product
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    # 'dismiss' is NOT a valid resolve action (separate endpoint) -> 422.
    assert client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "dismiss", "resolution_note": "x"},
    ).status_code == 422
    # blank note -> 422.
    assert client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "hold", "resolution_note": "  "},
    ).status_code == 422


def test_acknowledge_blank_reason_422(
    client: TestClient, db_session, admin, make_product
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    assert client.post(
        f"{BASE}/alerts/{alert_id}/acknowledge", headers=_auth(admin),
        json={"reason": ""},
    ).status_code == 422


# ===================================================================== #
# Aggregate — GET /admin/regulatory/aggregate (F2.27.5)
# ===================================================================== #


_AGGREGATE = f"{BASE}/aggregate"

_STATUS_KEYS = {"open", "acknowledged", "actioned", "dismissed"}
_SEVERITY_KEYS = {"low", "medium", "high", "critical"}
_ACTION_KEYS = {"none", "hold", "ban"}


def test_aggregate_non_admin_403(client: TestClient, db_session: Session):
    user = central_make_user(
        db_session, role=UserRole.manager, store_id=None
    )
    assert client.get(_AGGREGATE, headers=_auth(user)).status_code == 403


def test_aggregate_anonymous_401(client: TestClient):
    assert client.get(_AGGREGATE).status_code == 401


def test_aggregate_empty_state_dense(client: TestClient, admin: User):
    resp = client.get(_AGGREGATE, headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "total",
        "by_status",
        "by_severity",
        "by_recommended_action",
    }
    assert body["total"] == 0
    # Dense-by-enum: every member present, zero-filled.
    assert set(body["by_status"].keys()) == _STATUS_KEYS
    assert set(body["by_severity"].keys()) == _SEVERITY_KEYS
    assert set(body["by_recommended_action"].keys()) == _ACTION_KEYS
    assert all(v == 0 for v in body["by_status"].values())
    assert all(v == 0 for v in body["by_severity"].values())
    assert all(v == 0 for v in body["by_recommended_action"].values())


def test_aggregate_counts_match_seeded_alert(
    client: TestClient, db_session: Session, admin: User, make_product
):
    # One name-matched open/high/hold alert via the real pipeline.
    _open_alert_id(client, admin, db_session, make_product)

    resp = client.get(_AGGREGATE, headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["by_status"]["open"] == 1
    assert body["by_severity"]["high"] == 1
    assert body["by_recommended_action"]["hold"] == 1


def test_aggregate_respects_filters(
    client: TestClient, db_session: Session, admin: User, make_product
):
    _open_alert_id(client, admin, db_session, make_product)

    # Matching filter keeps the alert in the totals.
    match = client.get(
        _AGGREGATE, headers=_auth(admin), params={"status": "open"}
    )
    assert match.status_code == 200
    assert match.json()["total"] == 1

    # Non-matching filter excludes it (aggregate honors the same surface as
    # the list endpoint).
    miss = client.get(
        _AGGREGATE, headers=_auth(admin), params={"status": "dismissed"}
    )
    assert miss.status_code == 200
    assert miss.json()["total"] == 0
    assert miss.json()["by_status"]["open"] == 0


def test_aggregate_independent_of_list_pagination(
    client: TestClient, db_session: Session, admin: User, make_product
):
    # Two distinct alerts via two name-matched notices.
    _open_alert_id(client, admin, db_session, make_product, name="Vape One")
    _open_alert_id(client, admin, db_session, make_product, name="Vape Two")

    # A paginated list of size 1 does not shrink the aggregate.
    page = client.get(
        f"{BASE}/alerts", headers=_auth(admin), params={"limit": 1, "offset": 0}
    )
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] == 2

    agg = client.get(_AGGREGATE, headers=_auth(admin))
    assert agg.json()["total"] == 2
    assert agg.json()["by_status"]["open"] == 2


# ===================================================================== #
# Decision trail — GET /alerts/{alert_id}/decisions
# ===================================================================== #


_DECISIONS = "{base}/alerts/{aid}/decisions"


def test_decisions_rbac_anonymous_401(
    client: TestClient, db_session, admin, make_product
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    resp = client.get(_DECISIONS.format(base=BASE, aid=alert_id))
    assert resp.status_code == 401


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_decisions_rbac_non_admin_403(
    client: TestClient, db_session, admin, make_product, role: UserRole
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    user = central_make_user(db_session, role=role, store_id=None)
    resp = client.get(
        _DECISIONS.format(base=BASE, aid=alert_id), headers=_auth(user)
    )
    assert resp.status_code == 403


def test_decisions_missing_alert_404(client: TestClient, admin: User):
    resp = client.get(
        _DECISIONS.format(base=BASE, aid=uuid.uuid4()), headers=_auth(admin)
    )
    assert resp.status_code == 404


def test_decisions_empty_for_untouched_alert(
    client: TestClient, db_session, admin, make_product
):
    # A freshly created alert has no lifecycle decisions yet.
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    resp = client.get(
        _DECISIONS.format(base=BASE, aid=alert_id), headers=_auth(admin)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["limit"] == 25
    assert body["offset"] == 0


def test_decisions_shape_and_admin_can_list(
    client: TestClient, db_session, admin, make_product
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    ack = client.post(
        f"{BASE}/alerts/{alert_id}/acknowledge", headers=_auth(admin),
        json={"reason": "reviewing"},
    )
    assert ack.status_code == 200

    resp = client.get(
        _DECISIONS.format(base=BASE, aid=alert_id), headers=_auth(admin)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert {
        "id", "alert_id", "notice_id", "product_id", "actor_user_id",
        "action", "before", "after", "metadata", "reason", "created_at",
    } <= row.keys()
    assert row["alert_id"] == str(alert_id)
    assert row["action"] == "alert_acknowledged"
    assert row["actor_user_id"] == str(admin.id)
    assert row["reason"] == "reviewing"


def _assert_contract_ordering(items: list[dict]) -> None:
    """Documented order: created_at DESC, then id ASC as a stable tie-break.

    The test harness runs each test in one DB transaction, so `func.now()`
    (created_at) is identical for rows written in the same test; the id ASC
    tie-break is what makes the order deterministic. This asserts the contract
    directly rather than assuming wall-clock separation between decisions.
    """
    for prev, cur in zip(items, items[1:]):
        assert prev["created_at"] >= cur["created_at"]
        if prev["created_at"] == cur["created_at"]:
            assert prev["id"] < cur["id"]


def test_decisions_stable_documented_ordering(
    client: TestClient, db_session, admin, make_product
):
    # Two sequential decisions: acknowledge then resolve(no_action).
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    client.post(
        f"{BASE}/alerts/{alert_id}/acknowledge", headers=_auth(admin),
        json={"reason": "first"},
    )
    client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "no_action", "resolution_note": "second"},
    )

    url = _DECISIONS.format(base=BASE, aid=alert_id)
    first = client.get(url, headers=_auth(admin))
    assert first.status_code == 200
    items = first.json()["items"]
    assert len(items) == 2
    assert {i["action"] for i in items} == {
        "alert_acknowledged", "alert_resolved_no_action",
    }
    # Documented ordering contract holds.
    _assert_contract_ordering(items)
    # Stable: a second identical request returns the same order.
    second = client.get(url, headers=_auth(admin)).json()["items"]
    assert [i["id"] for i in second] == [i["id"] for i in items]


def test_decisions_only_for_requested_alert(
    client: TestClient, db_session, admin, make_product
):
    # Two distinct alerts, each with one decision; the endpoint must scope.
    _, alert_a = _open_alert_id(
        client, admin, db_session, make_product, name="Vape A"
    )
    _, alert_b = _open_alert_id(
        client, admin, db_session, make_product, name="Vape B"
    )
    client.post(
        f"{BASE}/alerts/{alert_a}/acknowledge", headers=_auth(admin),
        json={"reason": "a-only"},
    )
    client.post(
        f"{BASE}/alerts/{alert_b}/dismiss", headers=_auth(admin),
        json={"reason": "b-only"},
    )

    body = client.get(
        _DECISIONS.format(base=BASE, aid=alert_a), headers=_auth(admin)
    ).json()
    assert body["total"] == 1
    assert all(r["alert_id"] == str(alert_a) for r in body["items"])
    assert body["items"][0]["reason"] == "a-only"


def test_decisions_pagination(
    client: TestClient, db_session, admin, make_product
):
    _, alert_id = _open_alert_id(client, admin, db_session, make_product)
    # Produce two decisions (acknowledge, then resolve).
    client.post(
        f"{BASE}/alerts/{alert_id}/acknowledge", headers=_auth(admin),
        json={"reason": "first"},
    )
    client.post(
        f"{BASE}/alerts/{alert_id}/resolve", headers=_auth(admin),
        json={"action": "no_action", "resolution_note": "second"},
    )

    url = _DECISIONS.format(base=BASE, aid=alert_id)
    full = client.get(url, headers=_auth(admin)).json()["items"]
    page1 = client.get(
        url, headers=_auth(admin), params={"limit": 1, "offset": 0}
    ).json()
    page2 = client.get(
        url, headers=_auth(admin), params={"limit": 1, "offset": 1}
    ).json()

    assert page1["total"] == 2 and page2["total"] == 2
    assert page1["limit"] == 1 and page1["offset"] == 0
    assert page2["offset"] == 1
    assert len(page1["items"]) == 1 and len(page2["items"]) == 1
    # Pages slice the same documented order, no overlap.
    assert page1["items"][0]["id"] == full[0]["id"]
    assert page2["items"][0]["id"] == full[1]["id"]
    assert page1["items"][0]["id"] != page2["items"][0]["id"]


def test_decisions_read_only_no_mutation_and_no_operational_audit(
    client: TestClient, db_session, admin, make_product
):
    product, alert_id = _open_alert_id(
        client, admin, db_session, make_product
    )
    # One decision so there is something to read back.
    client.post(
        f"{BASE}/alerts/{alert_id}/acknowledge", headers=_auth(admin),
        json={"reason": "reviewing"},
    )

    from app.db.models import ComplianceAlert

    before_alert = db_session.get(ComplianceAlert, uuid.UUID(str(alert_id)))
    db_session.refresh(before_alert)
    status_before = before_alert.status
    updated_before = before_alert.updated_at
    compliance_before = product.compliance_status
    allowed_before = product.allowed_for_sale
    op_audit_before = db_session.scalar(
        select(func.count()).select_from(OperationalAuditLog)
    )

    resp = client.get(
        _DECISIONS.format(base=BASE, aid=alert_id), headers=_auth(admin)
    )
    assert resp.status_code == 200

    # Alert unchanged.
    db_session.expire_all()
    after_alert = db_session.get(ComplianceAlert, uuid.UUID(str(alert_id)))
    assert after_alert.status == status_before
    assert after_alert.updated_at == updated_before
    # Product unchanged.
    db_session.refresh(product)
    assert product.compliance_status == compliance_before
    assert product.allowed_for_sale == allowed_before
    # No operational audit rows created by a read.
    assert db_session.scalar(
        select(func.count()).select_from(OperationalAuditLog)
    ) == op_audit_before
    # No product compliance audit rows created by a read.
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


# ===================================================================== #
# Source ingestion — trigger + run observability (F2.27.7.C)
# ===================================================================== #


def _fda_raw(**over) -> dict:
    item = {
        "document_number": f"FDA-{uuid.uuid4().hex[:10]}",
        "document_type": "enforcement_notice",
        "title": "FDA enforcement notice",
        "publication_date": "2024-09-15",
        "url": "https://www.fda.gov/example",
        "products": [
            {
                "product_name": "Example Vape",
                "brand": "B",
                "category": "ENDS",
                "upc": "812345678901",
                "item_number": "SKU-1",
                "flavor": "Mint",
            }
        ],
    }
    item.update(over)
    return item


@pytest.fixture
def inject_fda_client(monkeypatch):
    """Patch the orchestrator's client resolver to a no-network static client.

    API tests never perform real network: the admin trigger endpoint resolves
    its client through `regulatory_ingestion.resolve_source_client`, which we
    replace with an in-memory `StaticRegulatorySourceClient`.
    """

    def _install(items: list[dict]) -> None:
        monkeypatch.setattr(
            _ingestion_svc,
            "resolve_source_client",
            lambda source: StaticRegulatorySourceClient(items),
        )

    return _install


def _fda_source(client: TestClient, admin: User, **over) -> dict:
    return _make_source(client, admin, kind="fda_enforcement", **over)


def test_admin_can_trigger_ingestion(
    client: TestClient, admin: User, inject_fda_client
):
    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin)
    resp = client.post(
        f"{BASE}/sources/{source['id']}/ingest", headers=_auth(admin)
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert set(body.keys()) == {"run", "items"}
    run = body["run"]
    assert run["source_id"] == source["id"]
    assert run["trigger"] == "manual"
    assert run["status"] == "succeeded"
    assert run["items_seen"] == 1
    assert run["items_created"] == 1
    assert run["items_deduped"] == 0
    assert run["items_failed"] == 0
    assert run["actor_user_id"] == str(admin.id)
    assert len(body["items"]) == 1
    assert body["items"][0]["outcome"] == "created"


def test_trigger_accepts_pipeline_flags(
    client: TestClient, admin: User, inject_fda_client
):
    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin)
    resp = client.post(
        f"{BASE}/sources/{source['id']}/ingest",
        headers=_auth(admin),
        json={"detect_matches": False, "create_alerts": False},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["run"]["matches_created"] == 0
    assert resp.json()["run"]["alerts_created"] == 0


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_non_admin_cannot_trigger_ingestion(
    client: TestClient, db_session: Session, admin: User, role: UserRole,
    inject_fda_client,
):
    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin)
    user = central_make_user(db_session, role=role, store_id=None)
    resp = client.post(
        f"{BASE}/sources/{source['id']}/ingest", headers=_auth(user)
    )
    assert resp.status_code == 403


def test_anonymous_cannot_trigger_ingestion(
    client: TestClient, admin: User
):
    source = _fda_source(client, admin)
    resp = client.post(f"{BASE}/sources/{source['id']}/ingest")
    assert resp.status_code == 401


def test_store_user_cannot_access_ingestion_endpoints(
    client: TestClient, db_session: Session, admin: User, inject_fda_client
):
    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin)
    store = Store(name="Store", code=f"st-{uuid.uuid4().hex[:8]}")
    db_session.add(store)
    db_session.commit()
    staff = central_make_user(
        db_session, role=UserRole.staff, store_id=store.id
    )

    assert client.post(
        f"{BASE}/sources/{source['id']}/ingest", headers=_auth(staff)
    ).status_code == 403
    assert client.get(
        f"{BASE}/sources/{source['id']}/ingestion-runs",
        headers=_auth(staff),
    ).status_code == 403
    assert client.get(
        f"{BASE}/ingestion-runs/{uuid.uuid4()}", headers=_auth(staff)
    ).status_code == 403


def test_admin_can_list_ingestion_runs(
    client: TestClient, admin: User, inject_fda_client
):
    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin)
    client.post(
        f"{BASE}/sources/{source['id']}/ingest", headers=_auth(admin)
    )
    resp = client.get(
        f"{BASE}/sources/{source['id']}/ingestion-runs", headers=_auth(admin)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["total"] == 1
    assert body["items"][0]["source_id"] == source["id"]


def test_admin_can_read_ingestion_run_detail(
    client: TestClient, admin: User, inject_fda_client
):
    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin)
    triggered = client.post(
        f"{BASE}/sources/{source['id']}/ingest", headers=_auth(admin)
    ).json()
    run_id = triggered["run"]["id"]

    resp = client.get(
        f"{BASE}/ingestion-runs/{run_id}", headers=_auth(admin)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["run"]["id"] == run_id
    assert len(body["items"]) == 1
    assert body["items"][0]["outcome"] == "created"


def test_trigger_inactive_source_returns_409(
    client: TestClient, admin: User, inject_fda_client
):
    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin, is_active=False)
    resp = client.post(
        f"{BASE}/sources/{source['id']}/ingest", headers=_auth(admin)
    )
    assert resp.status_code == 409, resp.text


def test_trigger_missing_source_returns_404(
    client: TestClient, admin: User, inject_fda_client
):
    inject_fda_client([_fda_raw()])
    resp = client.post(
        f"{BASE}/sources/{uuid.uuid4()}/ingest", headers=_auth(admin)
    )
    assert resp.status_code == 404, resp.text


def test_run_detail_missing_returns_404(client: TestClient, admin: User):
    resp = client.get(
        f"{BASE}/ingestion-runs/{uuid.uuid4()}", headers=_auth(admin)
    )
    assert resp.status_code == 404, resp.text


def test_trigger_returns_409_when_run_already_running(
    client: TestClient, db_session: Session, admin: User, inject_fda_client
):
    from datetime import UTC
    from datetime import datetime

    from app.db.models import RegulatoryIngestionRun

    inject_fda_client([_fda_raw()])
    source = _fda_source(client, admin)
    running = RegulatoryIngestionRun(
        source_id=uuid.UUID(source["id"]),
        trigger="manual",
        status="running",
        started_at=datetime.now(UTC),
    )
    db_session.add(running)
    db_session.commit()

    resp = client.post(
        f"{BASE}/sources/{source['id']}/ingest", headers=_auth(admin)
    )
    assert resp.status_code == 409, resp.text
