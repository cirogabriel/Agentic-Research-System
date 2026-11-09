
from __future__ import annotations

import logging
import threading
from typing import Protocol

from ars.config import Settings
from ars.schemas.rag import ScoredChunk

log = logging.getLogger(__name__)


class Reranker(Protocol):
    enabled: bool

    def rerank(
        self, query: str, chunks: list[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]: ...


class NoopReranker:
    enabled = False

    def rerank(
        self, query: str, chunks: list[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]:
        return chunks[:top_k]


class CrossEncoderReranker:


    enabled = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._lock = threading.Lock()

    def _load(
        self,
    ):  # carga perezosa: no se descarga el modelo hasta el primer uso
        with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder

                log.info(
                    "Cargando cross-encoder %s", self.settings.rerank_model
                )
                self._model = CrossEncoder(
                    self.settings.rerank_model,
                    device=self.settings.rerank_device,
                )
        return self._model

    def rerank(
        self, query: str, chunks: list[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]:
        if len(chunks) <= 1:
            return chunks[:top_k]
        model = self._load()
        scores = model.predict(
            [(query, c.content) for c in chunks],
            batch_size=self.settings.rerank_batch_size,
            show_progress_bar=False,
        )
        ranked = sorted(
            zip(chunks, scores, strict=True),
            key=lambda x: float(x[1]),
            reverse=True,
        )
        return [
            c.model_copy(
                update={
                    "score": float(s),
                    "rerank_score": float(s),
                    "source": "rerank",
                }
            )
            for c, s in ranked[:top_k]
        ]


def build_reranker(settings: Settings) -> Reranker:
    return (
        CrossEncoderReranker(settings)
        if settings.rerank_enabled
        else NoopReranker()
    )
