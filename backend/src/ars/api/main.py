from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ars import __version__
from ars.api.routes import documents, evaluations, research, system
from ars.config import get_settings
from ars.exceptions import (
    ARSError,
    BudgetExceededError,
    ConfigurationError,
    ConflictError,
    FileValidationError,
    NotFoundError,
)
from ars.logging_config import configure_logging
from ars.runtime import AppContainer

log = logging.getLogger(__name__)

_STATUS = {
    NotFoundError: 404, 
    ConflictError: 409, 
    FileValidationError: 422, 
    BudgetExceededError: 402, 
    ConfigurationError: 500
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    container = AppContainer.from_settings(settings)
    app.state.container = container
    try:
        container.verify_schema()
    except Exception as exc:  
        log.error("Verificación del esquema falló: %s", exc)
    interrupted = container.research.mark_interrupted_on_startup()
    if interrupted:
        log.warning(
            "Investigaciones marcadas como interrumpidas tras el reinicio: %s", 
            interrupted
        )
    yield
    container.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Agentic Research System", 
        version=__version__, 
        lifespan=lifespan,
        description="Plataforma backend de investigación multiagente.")
    
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware, 
            allow_origins=settings.cors_origins, 
            allow_methods=["*"], 
            allow_headers=["*"]
        )

    @app.exception_handler(ARSError)
    async def ars_error_handler(_: Request, exc: ARSError) -> JSONResponse:
        code = next((c for t, c in _STATUS.items() if isinstance(exc, t)), 500)
        if code >= 500:
            log.exception("Error interno")
        return JSONResponse(
            status_code=code, 
            content={"detail": str(exc)}
        )

    for module in (research, documents, evaluations, system):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
