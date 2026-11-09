
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ars.config import Settings
from ars.exceptions import ExtractionError
from ars.llm.budget import UsageTracker
from ars.rag.chunking import ChunkingConfig, TextChunker
from ars.rag.cleaning import CLEANING_VERSION, clean_text
from ars.rag.embeddings import EmbeddingService
from ars.rag.loaders import ExtractedDocument, Page, extract
from ars.security import detect_injection
from ars.utils.text import sha256_hex

log = logging.getLogger(__name__)


@dataclass
class IndexedContent:
    extracted: ExtractedDocument
    rows: list[dict[str, Any]]  # listas para insertar en document_chunks


def index_signature(settings: Settings) -> str:
   
    cfg = ChunkingConfig.from_settings(settings)
    payload = {
        "chunk": [cfg.strategy, cfg.size, cfg.overlap, list(cfg.separators)],
        "embedding": [settings.embedding_model, settings.embedding_dimensions],
        "cleaning": CLEANING_VERSION,
    }
    return sha256_hex(json.dumps(payload, sort_keys=True))


class IndexingPipeline:
    def __init__(
        self, settings: Settings, embeddings: EmbeddingService
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.chunker = TextChunker(ChunkingConfig.from_settings(settings))

    def run(
        self, file_type: str, data: bytes, tracker: UsageTracker | None = None
    ) -> IndexedContent:
        extracted = extract(
            file_type, data, max_pdf_pages=self.settings.max_pdf_pages
        )
        pages = [Page(clean_text(p.text), p.number) for p in extracted.pages]
        pages = [p for p in pages if p.text]
        if not pages:
            raise ExtractionError(
                "No se pudo extraer texto del documento (¿PDF escaneado sin OCR?)"
            )
        extracted.pages = pages
        chunks = self.chunker.split_pages(pages)
        vectors = self.embeddings.embed_documents(
            [c.text for c in chunks], tracker
        )  # un único flujo por lotes
        rows: list[dict[str, Any]] = []
        for chunk, vec in zip(chunks, vectors, strict=True):
            suspicious = detect_injection(chunk.text)
            if suspicious:
                log.warning(
                    "Chunk con patrones de prompt-injection",
                    extra={"chunk_index": chunk.index},
                )
            rows.append(
                {
                    "chunk_index": chunk.index,
                    "page_number": chunk.page_number,
                    "content": chunk.text,
                    "char_count": len(chunk.text),
                    "token_estimate": chunk.token_estimate,
                    "embedding": vec,
                    "extra": {"suspicious": True} if suspicious else {},
                }
            )
        return IndexedContent(extracted=extracted, rows=rows)
