from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.core.config import get_app_settings


settings = get_app_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
)

app.include_router(auth_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
