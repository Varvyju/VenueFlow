"""
VenueFlow – Main FastAPI application.
Smart Stadium Experience Platform for large-scale sporting venues.

Tackles: crowd movement, wait times, real-time coordination.
Google Services: Vertex AI Gemini, Google Maps, Cloud Translation, Firebase, Cloud Run.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from models.schemas import HealthResponse
from routers import fan, staff
from utils.config import get_settings

# ─────────────────────── Logging ─────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────── Lifespan ────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("VenueFlow %s starting up.", settings.app_version)
    logger.info("GCP project: %s | Location: %s", settings.gcp_project_id, settings.gcp_location)

    # Warm up Firebase zones on startup
    try:
        from services.firebase_service import get_firebase_service
        firebase = get_firebase_service()
        firebase.seed_zones()
        logger.info("Firebase zones seeded on startup.")
    except Exception as exc:
        logger.warning("Firebase startup seed failed (non-fatal): %s", exc)

    yield  # App runs here

    logger.info("VenueFlow shutting down.")


# ─────────────────────── App factory ─────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="VenueFlow API",
        description=(
            "Smart Stadium Experience Platform. "
            "Powered by Vertex AI Gemini, Google Maps, Cloud Translation, and Firebase."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next) -> Response:
        """Attach X-Process-Time header for latency observability."""
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
        return response

    # ── Exception handlers ────────────────────────────────────

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "type": "validation_error"},
        )

    # ── Routers ───────────────────────────────────────────────

    app.include_router(fan.router)
    app.include_router(staff.router)

    # ── Health check ──────────────────────────────────────────

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Service health check",
    )
    async def health_check() -> HealthResponse:
        """
        Returns service status. Used by Cloud Run health probes.
        Checks connectivity to each Google service.
        """
        service_status: dict[str, bool] = {}

        # Gemini / Vertex AI
        try:
            from services.gemini_service import get_gemini_service
            get_gemini_service()
            service_status["vertex_ai"] = True
        except Exception:
            service_status["vertex_ai"] = False

        # Firebase
        try:
            from services.firebase_service import get_firebase_service
            get_firebase_service()
            service_status["firebase"] = True
        except Exception:
            service_status["firebase"] = False

        # Maps
        try:
            from services.maps_service import get_maps_service
            get_maps_service()
            service_status["google_maps"] = True
        except Exception:
            service_status["google_maps"] = False

        # Translation
        try:
            from services.translation_service import get_translation_service
            get_translation_service()
            service_status["cloud_translation"] = True
        except Exception:
            service_status["cloud_translation"] = False

        overall = "healthy" if all(service_status.values()) else "degraded"

        return HealthResponse(
            status=overall,
            version=get_settings().app_version,
            services=service_status,
        )

    @app.get("/", tags=["Root"], summary="API root")
    async def root() -> dict:
        return {
            "name": "VenueFlow API",
            "version": get_settings().app_version,
            "description": "Smart Stadium Experience Platform",
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
