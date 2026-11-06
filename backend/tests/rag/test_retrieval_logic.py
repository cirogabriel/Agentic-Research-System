import uuid

from ars.config import Settings
from ars.rag.cache import TTLCache
from ars.rag.retrieval import rrf_fuse, union_best
from ars.rag.routing import QueryRouter
from ars.schemas.rag import ScoredChunk


def chunk(cid: uuid.UUID, score: float = 0.0) -> ScoredChunk:
    return ScoredChunk(chunk_id=cid, document_id=uuid.uuid4(), document_name="d", chunk_index=0, content="x", score=score)


def test_rrf_rewards_agreement_between_rankings():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    vec = [chunk(a), chunk(b), chunk(c)]
    kw = [chunk(c), chunk(a)]
    fused = rrf_fuse([vec, kw], k=60)
    assert [x.chunk_id for x in fused][:2] == [a, c]  # a (1º y 2º) y c (3º y 1º) superan a b
    assert abs(fused[0].score - (1 / 61 + 1 / 62)) < 1e-9
    assert rrf_fuse([vec, kw], top_n=1)[0].chunk_id == a


def test_union_best_keeps_highest_score_without_duplicates():
    a = uuid.uuid4()
    merged = union_best([[chunk(a, 0.2)], [chunk(a, 0.9), chunk(uuid.uuid4(), 0.5)]], 5)
    assert len(merged) == 2 and merged[0].score == 0.9


def test_router_rules():
    r = QueryRouter(Settings(_env_file=None))
    assert r.route("Compara la subducción plana con la subducción normal en los Andes").transform == "rag_fusion"
    assert r.route("sismos").transform == "rewrite"
    d = r.route('¿Qué magnitud tuvo el terremoto de 1960 en Valdivia según el "catálogo"?')
    assert (d.strategy, d.transform) == ("hybrid", "none")
    d = r.route("Explica cómo se acumula la energía elástica en las zonas de subducción activas")
    assert (d.strategy, d.transform, d.used_llm) == ("vector", "none", False)


def test_router_respects_explicit_config_and_hyde_gate():
    r = QueryRouter(Settings(_env_file=None, hyde_enabled=False))
    d = r.route("Explica cómo se acumula la energía elástica en las zonas de subducción", strategy="keyword", transform="hyde")
    assert d.strategy == "keyword" and d.transform == "none" and "HyDE" in d.reason
    r2 = QueryRouter(Settings(_env_file=None, hyde_enabled=True))
    assert r2.route("Explica cómo se acumula la energía elástica", transform="hyde").transform == "hyde"


def test_ttl_cache_expiry_and_lru():
    cache: TTLCache[int] = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1); cache.set("b", 2); cache.set("c", 3)
    assert cache.get("a") is None and cache.get("c") == 3
    cache.clear()
    assert cache.get("c") is None
    assert TTLCache(0, 60).get("x") is None
