
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from ars.config import Settings
from ars.db.models import EmbeddingCache
from ars.db.session import session_scope
from ars.exceptions import LLMError
from ars.llm.budget import UsageTracker
from ars.rag.cache import TTLCache
from ars.utils.text import approx_tokens, sha256_hex

log = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def build_openai_embeddings(settings: Settings) -> OpenAIEmbeddings:
    kwargs: dict[str, Any] = {}
    if settings.embedding_model.startswith("text-embedding-3"):
     
        kwargs["dimensions"] = settings.embedding_dimensions
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key.get_secret_value() or None,
        base_url=settings.openai_base_url or None,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        chunk_size=settings.embedding_batch_size,
        **kwargs,
    )


class EmbeddingService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session] | None = None,
        client: EmbeddingClient | None = None,
    ) -> None:
        self.settings = settings
        self._sf = session_factory
        self._client: EmbeddingClient = client or build_openai_embeddings(
            settings
        )
        self._query_cache: TTLCache[list[float]] = TTLCache(512, 3600)
        self.stats = {
            "api_calls": 0,
            "cache_hits": 0,
            "texts_embedded": 0,
            "tokens_estimated": 0,
        }

    # ---- caché persistente ----
    def _load_cached(self, hashes: Sequence[str]) -> dict[str, list[float]]:
        if not self._sf or not hashes:
            return {}
        s = self.settings
        with session_scope(self._sf) as session:
            rows = session.execute(
                select(
                    EmbeddingCache.content_hash, EmbeddingCache.embedding
                ).where(
                    EmbeddingCache.model == s.embedding_model,
                    EmbeddingCache.dimensions == s.embedding_dimensions,
                    EmbeddingCache.content_hash.in_(list(hashes)),
                )
            ).all()
        return {h: [float(x) for x in vec] for h, vec in rows}

    def _store_cached(self, items: dict[str, list[float]]) -> None:
        if not self._sf or not items:
            return
        s = self.settings
        values = [
            {
                "content_hash": h,
                "model": s.embedding_model,
                "dimensions": s.embedding_dimensions,
                "embedding": v,
            }
            for h, v in items.items()
        ]
        with session_scope(self._sf) as session:
            session.execute(
                pg_insert(EmbeddingCache)
                .values(values)
                .on_conflict_do_nothing()
            )

    def _embed_remote(
        self, texts: list[str], tracker: UsageTracker | None
    ) -> list[list[float]]:
        try:
            vectors = self._client.embed_documents(
                texts
            )  
        except Exception as exc:
            raise LLMError(
                f"Fallo al generar embeddings: {type(exc).__name__}: {exc}"
            ) from exc
        tokens = sum(approx_tokens(t) for t in texts)
        self.stats["api_calls"] += max(
            1, -(-len(texts) // self.settings.embedding_batch_size)
        )
        self.stats["texts_embedded"] += len(texts)
        self.stats["tokens_estimated"] += tokens
        if tracker:
            tracker.charge_embedding(tokens)
        return vectors

    def embed_documents(
        self, texts: Sequence[str], tracker: UsageTracker | None = None
    ) -> list[list[float]]:
        hashes = [sha256_hex(t) for t in texts]
        unique: dict[str, str] = dict(
            zip(hashes, texts, strict=True)
        )  # textos repetidos se embeben una vez
        cached = self._load_cached(list(unique))
        self.stats["cache_hits"] += len(cached)
        missing = {h: t for h, t in unique.items() if h not in cached}
        if missing:
            vectors = self._embed_remote(list(missing.values()), tracker)
            fresh = dict(zip(missing.keys(), vectors, strict=True))
            self._store_cached(fresh)
            cached.update(fresh)
        return [cached[h] for h in hashes]

    def embed_query(
        self, text: str, tracker: UsageTracker | None = None
    ) -> list[float]:
        key = sha256_hex(f"{self.settings.embedding_model}:{text}")
        hit = self._query_cache.get(key)
        if hit is not None:
            self.stats["cache_hits"] += 1
            return hit
        vector = self.embed_documents([text], tracker)[0]
        self._query_cache.set(key, vector)
        return vector
