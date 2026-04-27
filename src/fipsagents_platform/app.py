"""FastAPI application factory.

Single-process service. Sub-routers live under ``/v1/feedback``,
``/v1/sessions``, ``/v1/traces``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings, get_settings
from .routes import feedback as feedback_routes
from .routes import sessions as sessions_routes
from .routes import traces as traces_routes
from .store_factory import (
    build_feedback_store,
    build_session_store,
    build_trace_store,
)
from .version import __version__

logger = logging.getLogger(__name__)


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings)
    logger.info(
        "fipsagents-platform starting backend=%s auth=%s",
        settings.backend,
        settings.auth_mode,
    )

    feedback_store = build_feedback_store(settings)
    session_store = build_session_store(settings)
    trace_store = build_trace_store(settings)
    app.state.feedback_store = feedback_store
    app.state.session_store = session_store
    app.state.trace_store = trace_store
    app.state.settings = settings

    try:
        yield
    finally:
        await feedback_store.close()
        await session_store.close()
        await trace_store.close()
        logger.info("fipsagents-platform shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="fipsagents-platform",
        description="Cross-agent platform service for fips-agents deployments",
        version=__version__,
        lifespan=lifespan,
    )

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}

    app.include_router(feedback_routes.router, prefix="/v1/feedback", tags=["feedback"])
    app.include_router(sessions_routes.router, prefix="/v1/sessions", tags=["sessions"])
    app.include_router(traces_routes.router, prefix="/v1/traces", tags=["traces"])

    return app


app = create_app()
