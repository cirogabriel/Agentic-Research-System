from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException, Request, status

from ars.config import Settings, get_settings
from ars.runtime import AppContainer
from ars.services.documents import DocumentService
from ars.services.evaluation import EvaluationService
from ars.services.research import ResearchService


def get_container(request: Request) -> AppContainer:
    return request.app.state.container  # type: ignore[no-any-return]


def get_research_service(c: AppContainer = Depends(get_container)) -> ResearchService:
    return c.research


def get_document_service(c: AppContainer = Depends(get_container)) -> DocumentService:
    return c.documents


def get_evaluation_service(c: AppContainer = Depends(get_container)) -> EvaluationService:
    return c.evaluation


def require_api_key(x_api_key: str | None = Header(default=None), settings: Settings = Depends(get_settings)) -> None:
    """Autenticación opcional por cabecera X-API-Key (solo si API_KEY está definida)."""
    if settings.api_key is None or not settings.api_key.get_secret_value():
        return
    if x_api_key is None or not hmac.compare_digest(x_api_key, settings.api_key.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida o ausente")
