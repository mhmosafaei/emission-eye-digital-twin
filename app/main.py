from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings
from app.database import init_db
from app.routers.baseline import router as baseline_router
from app.routers.features import router as features_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.records import router as records_router
from app.routers.windows import router as windows_router

settings = get_settings()

app = FastAPI(title=settings.service_name)
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(records_router)
app.include_router(features_router)
app.include_router(windows_router)
app.include_router(baseline_router)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
