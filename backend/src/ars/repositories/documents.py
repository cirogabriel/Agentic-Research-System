from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from ars.db.models import Document, DocumentChunk
from ars.schemas.rag import ScoredChunk, SearchFilters
from ars.utils.text import fts_terms


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, doc: Document) -> Document:
        self.s.add(doc)
        self.s.flush()
        return doc

    def get(self, document_id: uuid.UUID) -> Document | None:
        return self.s.get(Document, document_id)

    def get_by_hash(self, content_hash: str) -> Document | None:
        return self.s.scalar(select(Document).where(Document.content_hash == content_hash))

    def get_by_filename(self, filename: str) -> Document | None:
        return self.s.scalar(select(Document).where(Document.filename == filename))

    def list(self, *, limit: int = 50, offset: int = 0, file_type: str | None = None, status: str | None = None) -> tuple[list[Document], int]:
        stmt = select(Document)
        if file_type:
            stmt = stmt.where(Document.file_type == file_type)
        if status:
            stmt = stmt.where(Document.status == status)
        total = self.s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.s.scalars(stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)).all()
        return list(rows), total

    def search_metadata(self, text: str, limit: int = 10) -> list[Document]:
        like = f"%{text}%"
        stmt = select(Document).where(
            or_(Document.filename.ilike(like), Document.title.ilike(like), Document.author.ilike(like))
        )
        return list(self.s.scalars(stmt.order_by(Document.created_at.desc()).limit(limit)).all())

    def delete(self, doc: Document) -> None:
        self.s.delete(doc)
        self.s.flush()


def _apply_filters(stmt: Select[Any], filters: SearchFilters | None) -> Select[Any]:
    stmt = stmt.where(Document.status == "indexed")
    if not filters:
        return stmt
    if filters.document_ids:
        stmt = stmt.where(Document.id.in_(filters.document_ids))
    if filters.file_types:
        stmt = stmt.where(Document.file_type.in_([t.lower() for t in filters.file_types]))
    if filters.author:
        stmt = stmt.where(Document.author.ilike(f"%{filters.author}%"))
    if filters.date_from:
        stmt = stmt.where(Document.document_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Document.document_date <= filters.date_to)
    return stmt


def _to_scored(chunk: DocumentChunk, name: str, score: float, source: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_name=name,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        score=float(score),
        source=source,
    )


class ChunkRepository:
    """Escritura de chunks y las dos búsquedas base (vectorial y léxica) sobre PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self.s = session

    def replace_for_document(self, document_id: uuid.UUID, rows: Sequence[dict[str, Any]]) -> None:
        """Sustituye todos los chunks de un documento en la misma transacción (indexación atómica)."""
        self.s.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        self.s.add_all([DocumentChunk(document_id=document_id, **row) for row in rows])
        self.s.flush()

    def vector_search(self, embedding: Sequence[float], k: int, filters: SearchFilters | None = None) -> list[ScoredChunk]:
        distance = DocumentChunk.embedding.cosine_distance(list(embedding)).label("distance")
        stmt = select(DocumentChunk, Document.filename, distance).join(Document, Document.id == DocumentChunk.document_id)
        stmt = _apply_filters(stmt, filters).order_by(distance).limit(k)
        return [_to_scored(c, name, 1.0 - float(d), "vector") for c, name, d in self.s.execute(stmt).all()]

    def keyword_search(self, query: str, k: int, filters: SearchFilters | None = None) -> list[ScoredChunk]:
        terms = fts_terms(query)
        if not terms:
            return []
        # OR entre términos + ts_rank_cd: tolera consultas largas (un AND estricto casi nunca coincidiría).
        tsquery = func.to_tsquery("simple", " | ".join(terms))
        rank = func.ts_rank_cd(DocumentChunk.search_vector, tsquery).label("rank")
        stmt = (
            select(DocumentChunk, Document.filename, rank)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.search_vector.op("@@")(tsquery))
        )
        stmt = _apply_filters(stmt, filters).order_by(rank.desc()).limit(k)
        return [_to_scored(c, name, r, "keyword") for c, name, r in self.s.execute(stmt).all()]

    def get_many(self, ids: Sequence[uuid.UUID]) -> list[ScoredChunk]:
        if not ids:
            return []
        stmt = select(DocumentChunk, Document.filename).join(Document, Document.id == DocumentChunk.document_id).where(DocumentChunk.id.in_(ids))
        by_id = {c.id: _to_scored(c, name, 0.0, "lookup") for c, name in self.s.execute(stmt).all()}
        return [by_id[i] for i in ids if i in by_id]

    def for_document(self, document_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index).offset(offset).limit(limit)
        return list(self.s.scalars(stmt).all())

    def existing_ids(self, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        return set(self.s.scalars(select(DocumentChunk.id).where(DocumentChunk.id.in_(ids))).all())
