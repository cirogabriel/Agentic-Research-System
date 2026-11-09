from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from ars import __version__
from ars.api.deps import get_container, require_api_key
from ars.config import Settings, get_settings
from ars.db.session import (
    check_vector_dimension,
    ping,
    vector_extension_installed,
)
from ars.runtime import AppContainer

router = APIRouter(tags=["system"])


def _health(c: AppContainer) -> dict[str, Any]:
    db_ok = ping(c.session_factory)
    checks: dict[str, Any] = {"database": db_ok}
    if db_ok:
        try:
            checks["pgvector"] = vector_extension_installed(c.session_factory)
            check_vector_dimension(
                c.session_factory, c.settings.embedding_dimensions
            )
            checks["embedding_dimension"] = True
        except Exception as exc:
            checks["embedding_dimension"] = f"error: {str(exc)[:160]}"
    checks["openai_key_configured"] = bool(
        c.settings.openai_api_key.get_secret_value()
    )
    checks["checkpointing"] = c.checkpointer is not None
    healthy = (
        db_ok
        and checks.get("pgvector") is True
        and checks.get("embedding_dimension") is True
    )
    return {
        "status": "ok" if healthy else "degraded",
        "version": __version__,
        "checks": checks,
    }


@router.get("/health", summary="Estado del servicio y sus dependencias")
async def health(c: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return await run_in_threadpool(_health, c)


@router.get(
    "/configuration",
    dependencies=[Depends(require_api_key)],
    summary="Configuración efectiva (sin secretos)",
)
async def configuration(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return settings.public_dict()
