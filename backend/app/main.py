from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.orders import router as orders_router
from app.api.routes.products import router as products_router
from app.api.routes.products import variants_router
from app.api.routes.stores import router as stores_router
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

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(variants_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(stores_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
