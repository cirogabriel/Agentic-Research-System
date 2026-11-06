"""Gestión de documentos: registro, duplicados/versiones por hash, indexación, reindexado y borrado."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session, sessionmaker

from ars.config import Settings
from ars.db.models import Document
from ars.db.session import session_scope
from ars.enums import DocumentStatus
from ars.exceptions import NotFoundError
from ars.rag.cache import TTLCache
from ars.rag.ingestion import IndexingPipeline, index_signature
from ars.rag.validation import validate_upload
from ars.repositories.documents import ChunkRepository, DocumentRepository
from ars.repositories.research import utcnow
from ars.storage import FileStorage
from ars.utils.text import sha256_hex

log = logging.getLogger(__name__)
UploadAction = Literal["created", "updated", "duplicate"]


@dataclass
class UploadResult:
    document: Document
    action: UploadAction


class DocumentService:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session], storage: FileStorage, pipeline: IndexingPipeline, retrieval_cache: TTLCache | None = None) -> None:  # type: ignore[type-arg]
        self.settings, self._sf, self.storage, self.pipeline = settings, session_factory, storage, pipeline
        self._retrieval_cache = retrieval_cache

    def _invalidate_cache(self) -> None:
        if self._retrieval_cache is not None:
            self._retrieval_cache.clear()

    # ---- 1) registro rápido (síncrono en la petición HTTP) ----
    def register_upload(self, filename: str, data: bytes) -> UploadResult:
        """Valida, detecta duplicados (mismo hash) o nuevas versiones (mismo nombre, otro hash) y guarda el archivo."""
        name, kind = validate_upload(filename, data, self.settings)
        digest = sha256_hex(data)
        with session_scope(self._sf) as s:
            repo = DocumentRepository(s)
            same_content = repo.get_by_hash(digest)
            if same_content is not None:
                return UploadResult(same_content, "duplicate")  # no se reprocesa un contenido idéntico
            path = self.storage.save(digest, Path(name).suffix.lower(), data)
            existing = repo.get_by_filename(name)
            if existing is not None:
                old_path = existing.storage_path
                existing.content_hash, existing.storage_path, existing.size_bytes = digest, path, len(data)
                existing.file_type, existing.version = kind, existing.version + 1
                existing.status, existing.error = DocumentStatus.PROCESSING.value, None
                s.flush()
                if old_path != path:
                    self.storage.delete(old_path)
                return UploadResult(existing, "updated")
            doc = repo.add(Document(
                filename=name, file_type=kind, size_bytes=len(data), content_hash=digest, storage_path=path,
                status=DocumentStatus.PROCESSING.value, extra={},
            ))
            return UploadResult(doc, "created")

    # ---- 2) procesamiento pesado (se ejecuta en segundo plano) ----
    def process(self, document_id: uuid.UUID) -> None:
        with session_scope(self._sf) as s:
            doc = DocumentRepository(s).get(document_id)
            if doc is None:
                return
            path, kind = doc.storage_path, doc.file_type
        try:
            content = self.pipeline.run(kind, self.storage.read(path))
        except Exception as exc:  # cualquier fallo deja el documento en 'failed' con el motivo
            log.exception("Fallo indexando documento", extra={"document_id": str(document_id)})
            with session_scope(self._sf) as s:
                if (doc := DocumentRepository(s).get(document_id)) is not None:
                    doc.status, doc.error = DocumentStatus.FAILED.value, str(exc)[:1000]
            return
        ex = content.extracted
        with session_scope(self._sf) as s:  # chunks antiguos → nuevos en una sola transacción
            doc = DocumentRepository(s).get(document_id)
            if doc is None:
                return
            ChunkRepository(s).replace_for_document(document_id, content.rows)
            doc.title, doc.author, doc.document_date = (ex.title or doc.title), ex.author, ex.date
            doc.num_pages, doc.num_chunks = ex.num_pages, len(content.rows)
            doc.index_signature, doc.indexed_at = index_signature(self.settings), utcnow()
            doc.status, doc.error = DocumentStatus.INDEXED.value, None
        self._invalidate_cache()
        log.info("Documento indexado", extra={"document_id": str(document_id), "chunks": len(content.rows)})

    def ingest(self, filename: str, data: bytes) -> UploadResult:
        """Registro + indexación síncrona (scripts y pruebas)."""
        result = self.register_upload(filename, data)
        if result.action != "duplicate":
            self.process(result.document.id)
            result.document = self.get(result.document.id)
        return result

    # ---- consultas ----
    def get(self, document_id: uuid.UUID) -> Document:
        with session_scope(self._sf) as s:
            doc = DocumentRepository(s).get(document_id)
            if doc is None:
                raise NotFoundError(f"Documento {document_id} no encontrado")
            return doc

    def list(self, *, limit: int = 50, offset: int = 0, file_type: str | None = None, status: str | None = None) -> tuple[list[Document], int]:
        with session_scope(self._sf) as s:
            return DocumentRepository(s).list(limit=limit, offset=offset, file_type=file_type, status=status)

    def search_metadata(self, text: str, limit: int = 10) -> list[Document]:
        with session_scope(self._sf) as s:
            return DocumentRepository(s).search_metadata(text, limit)

    def content(self, document_id: uuid.UUID, offset: int = 0, max_chars: int = 8000) -> tuple[str, int, bool]:
        """Texto del documento reconstruido desde sus chunks (sin solapamiento duplicado exacto: se devuelven tal cual)."""
        with session_scope(self._sf) as s:
            doc = DocumentRepository(s).get(document_id)
            if doc is None:
                raise NotFoundError(f"Documento {document_id} no encontrado")
            chunks = ChunkRepository(s).for_document(document_id, 0, 100000)
            text = "\n\n".join(c.content for c in chunks)
        return text[offset: offset + max_chars], len(text), offset + max_chars < len(text)

    # ---- mantenimiento ----
    def delete(self, document_id: uuid.UUID) -> None:
        with session_scope(self._sf) as s:
            repo = DocumentRepository(s)
            doc = repo.get(document_id)
            if doc is None:
                raise NotFoundError(f"Documento {document_id} no encontrado")
            path = doc.storage_path
            repo.delete(doc)  # los chunks caen por ON DELETE CASCADE
        try:
            self.storage.delete(path)
        except (OSError, ValueError):
            log.warning("No se pudo borrar el archivo físico", extra={"path": path})
        self._invalidate_cache()

    def prepare_reindex(self, document_id: uuid.UUID, force: bool = False) -> tuple[Document, bool]:
        """Devuelve (documento, necesita_reindexar). Sin cambios de configuración ni contenido no se repite el trabajo."""
        with session_scope(self._sf) as s:
            doc = DocumentRepository(s).get(document_id)
            if doc is None:
                raise NotFoundError(f"Documento {document_id} no encontrado")
            up_to_date = doc.status == DocumentStatus.INDEXED.value and doc.index_signature == index_signature(self.settings)
            if up_to_date and not force:
                return doc, False
            doc.status, doc.error = DocumentStatus.PROCESSING.value, None
            return doc, True
