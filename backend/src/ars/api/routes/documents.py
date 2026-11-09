from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Response,
    UploadFile,
    status,
)

from ars.api.deps import get_container, get_document_service, require_api_key
from ars.exceptions import FileValidationError
from ars.runtime import AppContainer
from ars.schemas.api import (
    DocumentListOut,
    DocumentOut,
    DocumentUploadOut,
    ReindexOut,
)
from ars.services.documents import DocumentService
from starlette.concurrency import run_in_threadpool

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/upload",
    response_model=DocumentUploadOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Subir un documento",
)
async def upload(
    response: Response,
    file: UploadFile = File(...),
    c: AppContainer = Depends(get_container),
) -> DocumentUploadOut:
    limit = c.settings.max_upload_bytes
    data = await file.read(limit + 1)

    if len(data) > limit:
        raise FileValidationError(
            f"El archivo supera el límite de {c.settings.max_upload_mb} MB"
        )

    result = await run_in_threadpool(
        c.documents.register_upload, file.filename or "", data
    )

    if result.action == "duplicate":
        response.status_code = status.HTTP_200_OK
    else:
        c.runner.submit(c.documents.process, result.document.id)

    return DocumentUploadOut(
        document=DocumentOut.model_validate(result.document),
        action=result.action,
    )


@router.get("", response_model=DocumentListOut)
async def list_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    file_type: str | None = None,
    status_: str | None = Query(None, alias="status"),
    svc: DocumentService = Depends(get_document_service),
) -> DocumentListOut:

    rows, total = await run_in_threadpool(
        lambda: svc.list(
            limit=limit, offset=offset, file_type=file_type, status=status_
        )
    )

    return DocumentListOut(
        items=[DocumentOut.model_validate(d) for d in rows], total=total
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID, svc: DocumentService = Depends(get_document_service)
) -> DocumentOut:

    return DocumentOut.model_validate(
        await run_in_threadpool(svc.get, document_id)
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID, svc: DocumentService = Depends(get_document_service)
) -> Response:

    await run_in_threadpool(svc.delete, document_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/reindex",
    response_model=ReindexOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex(
    document_id: uuid.UUID,
    response: Response,
    force: bool = Query(False),
    c: AppContainer = Depends(get_container),
) -> ReindexOut:

    doc, needed = await run_in_threadpool(
        c.documents.prepare_reindex, document_id, force
    )

    if not needed:
        response.status_code = status.HTTP_200_OK
        return ReindexOut(
            document=DocumentOut.model_validate(doc), action="up_to_date"
        )

    c.runner.submit(c.documents.process, document_id)

    return ReindexOut(
        document=DocumentOut.model_validate(doc), action="reindexing"
    )
