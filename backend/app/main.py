from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin_compliance import router as admin_compliance_router
from app.api.routes.admin_dashboard import router as admin_dashboard_router
from app.api.routes.admin_earnings import router as admin_earnings_router
from app.api.routes.admin_operations import router as admin_operations_router
from app.api.routes.admin_products import router as admin_products_router
from app.api.routes.admin_regulatory import router as admin_regulatory_router
from app.api.routes.admin_settings import router as admin_settings_router
from app.api.routes.admin_store_applications import (
    router as admin_store_applications_router,
)
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.orders import router as orders_router
from app.api.routes.products import router as products_router
from app.api.routes.products import variants_router
from app.api.routes.public import router as public_router
from app.api.routes.store_dashboard import router as store_dashboard_router
from app.api.routes.store_earnings import router as store_earnings_router
from app.api.routes.store_regulatory import router as store_regulatory_router
from app.api.routes.stores import router as stores_router
from app.api.routes.users import router as users_router
from app.core.config import get_app_settings


settings = get_app_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(products_router)
app.include_router(variants_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(stores_router)
app.include_router(store_dashboard_router)
app.include_router(store_earnings_router)
app.include_router(store_regulatory_router)
app.include_router(audit_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_earnings_router)
app.include_router(admin_operations_router)
app.include_router(admin_products_router)
app.include_router(admin_regulatory_router)
app.include_router(admin_compliance_router)
app.include_router(admin_settings_router)
app.include_router(admin_store_applications_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
