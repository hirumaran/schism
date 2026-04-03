from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies import get_analysis_service, get_repository, get_vector_store
from app.logging_utils import configure_logging
from app.routers import analyze, export, health, jobs, search

settings = get_settings()
configure_logging(settings.log_level, settings.log_format)


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_repository()
    get_vector_store()
    analysis_service = get_analysis_service()
    await analysis_service.start_watchdog()
    try:
        yield
    finally:
        await analysis_service.stop_watchdog()


app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins if settings.allowed_origins else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(analyze.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(export.router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "api_prefix": settings.api_prefix,
        "docs": "/docs",
    }
