
import os
import uuid

import pytest
from fakes import FakeEmbeddingClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL no definida",
    ),
]


@pytest.fixture(scope="module")
def container():
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    from ars.config import get_settings

    get_settings.cache_clear()
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    from ars.rag.embeddings import EmbeddingService
    from ars.rag.reranker import NoopReranker
    from ars.runtime import AppContainer
    from ars.db.session import make_engine, make_session_factory
    from ars.tasks.runner import InlineRunner

    settings = get_settings().model_copy(
        update={"rerank_enabled": False, "openai_api_key": "x"}
    )
    engine = make_engine(settings)
    sf = make_session_factory(engine)
    emb = EmbeddingService(
        settings, sf, client=FakeEmbeddingClient(settings.embedding_dimensions)
    )
    c = AppContainer(
        settings, engine, sf, emb, NoopReranker(), InlineRunner(), None, None
    )
    yield c
    engine.dispose()


def test_orm_models_match_migration(container):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from ars.db.base import Base

    with container.engine.connect() as conn:
        diffs = compare_metadata(
            MigrationContext.configure(conn), Base.metadata
        )
    structural = [
        d
        for d in diffs
        if isinstance(d, tuple)
        and d[0] in {"add_table", "remove_table", "add_column", "remove_column"}
    ]
    assert structural == []


def test_ingest_dedupe_version_and_hybrid_search(container):
    docs = container.documents
    r1 = docs.ingest(
        "tectonica.md",
        "# Tectónica\n\nLa placa de Nazca subduce bajo la placa Sudamericana en los Andes.".encode(),
    )
    assert (
        r1.action == "created"
        and r1.document.status == "indexed"
        and r1.document.num_chunks >= 1
        and r1.document.title == "Tectónica"
    )
    assert (
        docs.ingest(
            "copia.md",
            "# Tectónica\n\nLa placa de Nazca subduce bajo la placa Sudamericana en los Andes.".encode(),
        ).action
        == "duplicate"
    )
    docs.ingest(
        "otro.md",
        b"# Cocina\n\nLa receta lleva harina, huevos y azucar para el pastel.",
    )
    calls_before = container.embeddings._client.calls  # noqa: SLF001
    assert (
        docs.ingest(
            "tectonica.md",
            "# Tectónica\n\nLa placa de Nazca subduce. Version dos del texto sobre los Andes.".encode(),
        ).action
        == "updated"
    )
    assert (
        docs.get(r1.document.id).version == 2
        and container.embeddings._client.calls == calls_before + 1
    )  # noqa: SLF001

    hits = container.retrieval.hybrid_search("placa Nazca subduce Andes", 3)
    assert hits and hits[0].document_name == "tectonica.md"
    assert (
        container.retrieval.keyword_search("harina pastel", 3)[0].document_name
        == "otro.md"
    )
    assert (
        container.retrieval.vector_search("receta de pastel con harina", 3)[
            0
        ].document_name
        == "otro.md"
    )

    doc, needed = docs.prepare_reindex(r1.document.id)
    assert needed is False or doc.status == "processing"
    docs.delete(r1.document.id)
    assert all(
        h.document_name != "tectonica.md"
        for h in container.retrieval.hybrid_search("placa Nazca", 5)
    )


def test_research_outcome_roundtrip(container):
    from ars.db.session import session_scope
    from ars.repositories.research import ResearchRepository
    from ars.schemas.api import ResearchOptions

    r = container.research.create(
        "¿Pregunta de prueba para persistencia?", ResearchOptions()
    )
    chunk_id, doc_id = str(uuid.uuid4()), str(uuid.uuid4())
    state = {
        "status": "completed",
        "stop_reason": "sufficient",
        "iteration": 1,
        "analysis": {"normalized_query": "q"},
        "tasks": [{"id": "t1", "title": "T", "question": "q", "iteration": 1}],
        "task_results": [
            {
                "task_id": "t1",
                "strategy": "hybrid",
                "queries": ["q"],
                "evidence": [{}],
            }
        ],
        "sources": {
            "S1": {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "document_name": "a.md",
                "text": "texto",
                "score": 1.0,
            }
        },
        "findings": [
            {
                "statement": "hecho",
                "kind": "fact",
                "labels": ["S1"],
                "support": "supported",
                "note": "",
            }
        ],
        "report": {
            "title": "Informe",
            "markdown": "# Informe",
            "summary": "resumen",
            "content": {},
        },
        "quality": {"citation_validity": 1.0},
    }
    usage = {
        "tokens_input": 10,
        "tokens_output": 5,
        "embedding_tokens": 2,
        "cost_usd": 0.0001,
    }
    with session_scope(container.session_factory) as s:
        ResearchRepository(s).save_outcome(r.id, state, usage)
    bundle = container.research.report_bundle(r.id)
    assert (
        bundle["title"] == "Informe"
        and bundle["findings"][0]["sources"] == ["S1"]
        and bundle["sources"][0].document_id is None
    )  # el chunk ya no existe
    assert container.research.get(r.id).status == "completed"
