"""HTTP layer for the store-scoped dashboard surfaces.

Thin routes: parse path/query, authorize via the established
`require_store_member` + `require_staff_or_above` pair (same pattern
the inventory / orders / audit endpoints use), delegate to
`app.services.store_dashboard`, return the service response unchanged.

Seven endpoints, all read-only, all scoped to one store:

  GET /stores/{store_id}/dashboard
  GET /stores/{store_id}/dashboard/kpis
  GET /stores/{store_id}/orders/summary
  GET /stores/{store_id}/inventory/summary
  GET /stores/{store_id}/products/summary
  GET /stores/{store_id}/activity
  GET /stores/{store_id}/alerts

Access matrix:

  admin / owner / manager / staff   →  allowed
  driver / anon                      →  denied

`driver` is intentionally excluded — the dashboard is an operational
surface for in-store decision making, while `driver` is the delivery
role and never sees aggregate KPIs / inventory state. This matches
`/stores/{store_id}/audit` and the store-scoped inventory endpoints.

Tenancy collisions with `/stores/{store_id}` (`stores.py`) are
avoided by distinct path suffixes; FastAPI routes are matched by
exact segments so no order-dependency exists.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import require_staff_or_above
from app.api.deps import require_store_member
from app.db.models import User
from app.db.session import get_db
from app.schemas.store_dashboard import StoreActivityListResponse
from app.schemas.store_dashboard import StoreAlertCategory
from app.schemas.store_dashboard import StoreAlertSeverity
from app.schemas.store_dashboard import StoreAlertsListResponse
from app.schemas.store_dashboard import StoreDashboardKpis
from app.schemas.store_dashboard import StoreDashboardSummary
from app.schemas.store_dashboard import StoreInventorySummary
from app.schemas.store_dashboard import StoreOrdersSummary
from app.schemas.store_dashboard import StoreProductsSummary
from app.services import store_dashboard as svc


router = APIRouter(tags=["store-dashboard"])


@router.get(
    "/stores/{store_id}/dashboard",
    response_model=StoreDashboardSummary,
    dependencies=[Depends(require_store_member)],
)
def get_store_dashboard_endpoint(
    store_id: UUID,
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreDashboardSummary:
    return svc.get_store_dashboard_summary(db, store_id=store_id)


@router.get(
    "/stores/{store_id}/dashboard/kpis",
    response_model=StoreDashboardKpis,
    dependencies=[Depends(require_store_member)],
)
def get_store_dashboard_kpis_endpoint(
    store_id: UUID,
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreDashboardKpis:
    return svc.get_store_dashboard_kpis(db, store_id=store_id)


@router.get(
    "/stores/{store_id}/orders/summary",
    response_model=StoreOrdersSummary,
    dependencies=[Depends(require_store_member)],
)
def get_store_orders_summary_endpoint(
    store_id: UUID,
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreOrdersSummary:
    return svc.get_store_orders_summary(db, store_id=store_id)


@router.get(
    "/stores/{store_id}/inventory/summary",
    response_model=StoreInventorySummary,
    dependencies=[Depends(require_store_member)],
)
def get_store_inventory_summary_endpoint(
    store_id: UUID,
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreInventorySummary:
    return svc.get_store_inventory_summary(db, store_id=store_id)


@router.get(
    "/stores/{store_id}/products/summary",
    response_model=StoreProductsSummary,
    dependencies=[Depends(require_store_member)],
)
def get_store_products_summary_endpoint(
    store_id: UUID,
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreProductsSummary:
    return svc.get_store_products_summary(db, store_id=store_id)


@router.get(
    "/stores/{store_id}/activity",
    response_model=StoreActivityListResponse,
    dependencies=[Depends(require_store_member)],
)
def list_store_activity_endpoint(
    store_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreActivityListResponse:
    return svc.list_store_activity(
        db,
        store_id=store_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/stores/{store_id}/alerts",
    response_model=StoreAlertsListResponse,
    dependencies=[Depends(require_store_member)],
)
def list_store_alerts_endpoint(
    store_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: StoreAlertCategory | None = Query(default=None),
    severity: StoreAlertSeverity | None = Query(default=None),
    aging_minutes: int = Query(default=60, ge=1),
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreAlertsListResponse:
    return svc.list_store_alerts(
        db,
        store_id=store_id,
        limit=limit,
        offset=offset,
        category=category,
        severity=severity,
        aging_minutes=aging_minutes,
    )
