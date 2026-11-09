
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session, sessionmaker

from ars.config import Settings
from ars.db.session import session_scope
from ars.exceptions import ARSError, BudgetExceededError
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord, UsageTracker
from ars.rag.cache import TTLCache
from ars.rag.embeddings import EmbeddingService
from ars.rag.query_transform import QueryTransformer
from ars.rag.reranker import Reranker
from ars.rag.routing import QueryRouter
from ars.repositories.documents import ChunkRepository
from ars.schemas.rag import (
    RetrievalRequest,
    RetrievalResult,
    ScoredChunk,
    SearchFilters,
    Strategy,
)
from ars.utils.text import sha256_hex

log = logging.getLogger(__name__)


def rrf_fuse(
    rankings: Sequence[Sequence[ScoredChunk]],
    k: int = 60,
    top_n: int | None = None,
) -> list[ScoredChunk]:

    scores: dict[uuid.UUID, float] = {}
    best: dict[uuid.UUID, ScoredChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (
                k + rank
            )
            best.setdefault(chunk.chunk_id, chunk)
    ordered = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    fused = [
        best[cid].model_copy(update={"score": scores[cid], "source": "fused"})
        for cid in ordered
    ]
    return fused[:top_n] if top_n else fused


def union_best(
    rankings: Sequence[Sequence[ScoredChunk]], top_n: int
) -> list[ScoredChunk]:

    best: dict[uuid.UUID, ScoredChunk] = {}
    for ranking in rankings:
        for c in ranking:
            if c.chunk_id not in best or c.score > best[c.chunk_id].score:
                best[c.chunk_id] = c
    return sorted(best.values(), key=lambda c: c.score, reverse=True)[:top_n]


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        embeddings: EmbeddingService,
        reranker: Reranker,
        router: QueryRouter | None = None,
        transformer: QueryTransformer | None = None,
    ) -> None:
        self.settings = settings
        self._sf = session_factory
        self.embeddings = embeddings
        self.reranker = reranker
        self.router = router or QueryRouter(settings)
        self.transformer = transformer or QueryTransformer(settings)
        self.cache: TTLCache[RetrievalResult] = TTLCache(
            settings.retrieval_cache_size, settings.retrieval_cache_ttl_seconds
        )

    # ---- búsquedas base ----
    def _vector(
        self,
        repo: ChunkRepository,
        text: str,
        k: int,
        filters: SearchFilters | None,
        tracker: UsageTracker | None,
    ) -> list[ScoredChunk]:
        return repo.vector_search(
            self.embeddings.embed_query(text, tracker), k, filters
        )

    def _search(
        self,
        repo: ChunkRepository,
        text: str,
        strategy: Strategy,
        k: int,
        filters: SearchFilters | None,
        tracker: UsageTracker | None,
    ) -> list[ScoredChunk]:
        if strategy == "vector":
            return self._vector(repo, text, k, filters, tracker)
        if strategy == "keyword":
            return repo.keyword_search(text, k, filters)
        return rrf_fuse(  # hybrid
            [
                self._vector(repo, text, k, filters, tracker),
                repo.keyword_search(text, k, filters),
            ],
            self.settings.rrf_k,
            k,
        )

    # ---- API pública simple  ----
    def vector_search(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
        tracker: UsageTracker | None = None,
    ) -> list[ScoredChunk]:
        with session_scope(self._sf) as s:
            return self._vector(
                ChunkRepository(s), query, top_k, filters, tracker
            )

    def keyword_search(
        self, query: str, top_k: int, filters: SearchFilters | None = None
    ) -> list[ScoredChunk]:
        with session_scope(self._sf) as s:
            return ChunkRepository(s).keyword_search(query, top_k, filters)

    def hybrid_search(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
        tracker: UsageTracker | None = None,
    ) -> list[ScoredChunk]:
        with session_scope(self._sf) as s:
            return self._search(
                ChunkRepository(s), query, "hybrid", top_k, filters, tracker
            )

    def rerank(
        self, query: str, chunks: list[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]:
        return self.reranker.rerank(query, chunks, top_k)

    # ---- pipeline completo ----
    def retrieve(
        self,
        req: RetrievalRequest,
        *,
        llm: StructuredLLM | None = None,
        tracker: UsageTracker | None = None,
        rec: ExecutionRecord | None = None,
    ) -> RetrievalResult:
        t0 = time.perf_counter()
        do_rerank = (
            self.settings.rerank_enabled if req.rerank is None else req.rerank
        )
        key = sha256_hex(
            f"{req.model_dump_json()}|{do_rerank}|{self.settings.retrieval_strategy}|{self.settings.query_transform}"
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached.model_copy(
                update={
                    "cache_hit": True,
                    "latency_ms": int((time.perf_counter() - t0) * 1000),
                    "llm_calls": 0,
                }
            )

        decision = self.router.route(
            req.query,
            strategy=req.strategy,
            transform=req.transform,
            llm=llm,
            rec=rec,
        )
        transform = decision.transform if llm is not None else "none"
        try:
            expanded = self.transformer.expand(req.query, transform, llm, rec)
        except BudgetExceededError:
            raise
        except ARSError as exc: 
            log.warning(
                "Transformación '%s' falló (%s); se usa la consulta original",
                transform,
                exc,
            )
            from ars.rag.query_transform import TransformResult

            expanded, transform = TransformResult([req.query]), "none"

        k_final = req.top_k
        k_candidates = (
            k_final * self.settings.rerank_candidate_multiplier
            if do_rerank
            else k_final
        )
        with session_scope(self._sf) as s:
            repo = ChunkRepository(s)
            rankings = [
                self._search(
                    repo,
                    q,
                    decision.strategy,
                    k_candidates,
                    req.filters,
                    tracker,
                )
                for q in expanded.queries
            ]
            if (
                expanded.hyde_passage
            ):  
                rankings.append(
                    self._vector(
                        repo,
                        expanded.hyde_passage,
                        k_candidates,
                        req.filters,
                        tracker,
                    )
                )

        if len(rankings) == 1:
            merged = rankings[0]
        elif transform == "multi_query":
            merged = union_best(rankings, k_candidates)
        else:  # rag_fusion, hyde
            merged = rrf_fuse(rankings, self.settings.rrf_k, k_candidates)

        reranked = bool(do_rerank and self.reranker.enabled and len(merged) > 1)
        chunks = (
            self.reranker.rerank(req.query, merged, k_final)
            if reranked
            else merged[:k_final]
        )

        if rec is not None:
            if transform != "none":
                rec.tool_calls.append(f"transform:{transform}")
            rec.tool_calls.append(f"{decision.strategy}_search")
            if reranked:
                rec.tool_calls.append("rerank")
        result = RetrievalResult(
            chunks=chunks,
            decision=decision.model_copy(update={"transform": transform}),  
            queries=expanded.queries
            + (
                [f"[hyde] {expanded.hyde_passage[:80]}…"]
                if expanded.hyde_passage
                else []
            ),
            latency_ms=int((time.perf_counter() - t0) * 1000),
            llm_calls=expanded.llm_calls,
            reranked=reranked,
        )
        self.cache.set(key, result)
        return result
