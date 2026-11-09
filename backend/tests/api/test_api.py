"""Pruebas de la API con servicios simulados """

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ars.api.deps import (
    get_container,
    get_document_service,
    get_evaluation_service,
    get_research_service,
)
from ars.api.main import create_app
from ars.config import Settings, get_settings
from ars.exceptions import ConflictError, FileValidationError, NotFoundError
from ars.tasks.runner import InlineRunner

NOW = datetime.now(UTC)


def research_row(**kw):
    base = dict(
        id=uuid.uuid4(),
        parent_id=None,
        query="consulta de prueba",
        status="pending",
        current_stage=None,
        stop_reason=None,
        clarification_questions=None,
        iterations=0,
        tokens_input=0,
        tokens_output=0,
        embedding_tokens=0,
        cost_usd=0.0,
        created_at=NOW,
        finished_at=None,
        started_at=None,
        error=None,
    )
    return SimpleNamespace(**{**base, **kw})


def doc_row(**kw):
    base = dict(
        id=uuid.uuid4(),
        filename="a.md",
        file_type="md",
        title=None,
        author=None,
        document_date=None,
        size_bytes=5,
        content_hash="h",
        version=1,
        status="processing",
        error=None,
        num_pages=None,
        num_chunks=0,
        created_at=NOW,
        updated_at=NOW,
        indexed_at=None,
    )
    return SimpleNamespace(**{**base, **kw})


class FakeResearch:
    def __init__(self):
        self.row = research_row()
        self.enqueued = []
        self.event_rows = [
            SimpleNamespace(
                id=1,
                event_type="research.started",
                message="m",
                payload={},
                created_at=NOW,
            ),
            SimpleNamespace(
                id=2,
                event_type="research.completed",
                message="fin",
                payload={},
                created_at=NOW,
            ),
        ]
        self.status = "completed"

    def create(self, query, options, parent_id=None):
        self.row = research_row(query=query)
        return self.row

    def enqueue(self, rid, **kw):
        self.enqueued.append(rid)

    def get(self, rid):
        if rid != self.row.id:
            raise NotFoundError("no existe")
        return self.row

    def list(self, limit, offset, status):
        return [self.row], 1

    def report_bundle(self, rid):
        self.get(rid)
        return {
            "research_id": rid,
            "title": "T",
            "markdown": "# T",
            "content": {},
            "quality": {},
            "sources": [],
            "findings": [],
            "created_at": NOW,
        }

    def events_after(self, rid, after):
        self.get(rid)
        return [e for e in self.event_rows if e.id > after], self.status

    def clarify(self, rid, answer):
        raise ConflictError("no espera aclaraciones")


class FakeDocs:
    def __init__(self):
        self.processed = []
        self.action = "created"

    def register_upload(self, filename, data):
        if filename.endswith(".exe"):
            raise FileValidationError("Tipo de archivo no soportado")
        return SimpleNamespace(
            document=doc_row(filename=filename), action=self.action
        )

    def process(self, doc_id):
        self.processed.append(doc_id)

    def get(self, doc_id):
        raise NotFoundError("no existe")

    def list(self, **kw):
        return [doc_row()], 1


@pytest.fixture
def ctx():
    app = create_app()
    research, docs = FakeResearch(), FakeDocs()
    container = SimpleNamespace(
        settings=Settings(_env_file=None, max_upload_mb=1),
        runner=InlineRunner(),
        documents=docs,
        checkpointer=None,
        session_factory=None,
    )
    app.state.container = container
    app.dependency_overrides[get_research_service] = lambda: research
    app.dependency_overrides[get_document_service] = lambda: docs
    app.dependency_overrides[get_evaluation_service] = lambda: SimpleNamespace()
    app.dependency_overrides[get_container] = lambda: container
    return SimpleNamespace(
        client=TestClient(app), research=research, docs=docs, app=app
    )


def test_create_research_returns_202_and_enqueues(ctx):
    r = ctx.client.post(
        "/api/v1/research",
        json={
            "query": "¿Por qué hay terremotos en los Andes?",
            "options": {"max_iterations": 2, "parallel": False},
        },
    )
    assert (
        r.status_code == 202
        and r.json()["status"] == "pending"
        and ctx.research.enqueued == [ctx.research.row.id]
    )


@pytest.mark.parametrize(
    "body",
    [
        {"query": "abc"},
        {"query": "x" * 5000},
        {"query": "consulta válida", "options": {"max_iterations": 99}},
        {},
    ],
)
def test_create_research_validation(ctx, body):
    assert ctx.client.post("/api/v1/research", json=body).status_code == 422


def test_status_report_and_not_found(ctx):
    rid = ctx.research.row.id
    assert (
        ctx.client.get(f"/api/v1/research/{rid}/status").json()["status"]
        == "pending"
    )
    assert (
        ctx.client.get(f"/api/v1/research/{rid}/report").json()["markdown"]
        == "# T"
    )
    assert (
        ctx.client.get(f"/api/v1/research/{rid}/report?format=markdown").text
        == "# T"
    )
    assert ctx.client.get(f"/api/v1/research/{uuid.uuid4()}").status_code == 404
    assert ctx.client.get("/api/v1/research/not-a-uuid").status_code == 422
    assert (
        ctx.client.post(
            f"/api/v1/research/{rid}/clarifications", json={"answer": "x"}
        ).status_code
        == 409
    )
    assert ctx.client.get("/api/v1/research?limit=5").json()["total"] == 1


def test_events_sse_and_json(ctx):
    rid = ctx.research.row.id
    body = ctx.client.get(f"/api/v1/research/{rid}/events").text
    assert (
        "event: research.started" in body
        and "event: research.completed" in body
        and "event: end" in body
    )
    after = ctx.client.get(
        f"/api/v1/research/{rid}/events", headers={"Last-Event-ID": "1"}
    ).text
    assert "research.started" not in after and "research.completed" in after
    assert (
        len(
            ctx.client.get(f"/api/v1/research/{rid}/events?stream=false").json()
        )
        == 2
    )


def test_document_upload_paths(ctx):
    r = ctx.client.post(
        "/api/v1/documents/upload",
        files={"file": ("a.md", b"# hola", "text/markdown")},
    )
    assert (
        r.status_code == 202
        and r.json()["action"] == "created"
        and len(ctx.docs.processed) == 1
    )
    ctx.docs.action = "duplicate"
    r = ctx.client.post(
        "/api/v1/documents/upload",
        files={"file": ("a.md", b"# hola", "text/markdown")},
    )
    assert (
        r.status_code == 200 and len(ctx.docs.processed) == 1
    )  # un duplicado no se vuelve a procesar
    assert (
        ctx.client.post(
            "/api/v1/documents/upload",
            files={"file": ("a.exe", b"x", "application/octet-stream")},
        ).status_code
        == 422
    )
    big = ctx.client.post(
        "/api/v1/documents/upload",
        files={"file": ("big.txt", b"x" * (2 * 1024 * 1024), "text/plain")},
    )
    assert big.status_code == 422
    assert (
        ctx.client.get("/api/v1/documents/" + str(uuid.uuid4())).status_code
        == 404
    )


def test_configuration_hides_secrets(ctx):
    ctx.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        openai_api_key="sk-secret-123",
        database_url="postgresql+psycopg://u:pw@h/db",
    )
    cfg = ctx.client.get("/api/v1/configuration").json()
    assert (
        cfg["openai_api_key"] == "configured"
        and "pw" not in cfg["database_url"]
        and "sk-secret" not in str(cfg)
    )
    assert cfg["llm_model"] == "gpt-4o-mini"


def test_api_key_protection(ctx):
    ctx.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, api_key="s3cret"
    )
    rid = ctx.research.row.id
    assert ctx.client.get(f"/api/v1/research/{rid}").status_code == 401
    assert (
        ctx.client.get(
            f"/api/v1/research/{rid}", headers={"X-API-Key": "bad"}
        ).status_code
        == 401
    )
    assert (
        ctx.client.get(
            f"/api/v1/research/{rid}", headers={"X-API-Key": "s3cret"}
        ).status_code
        == 200
    )


def test_openapi_lists_required_endpoints(ctx):
    paths = ctx.client.get("/openapi.json").json()["paths"]
    for p in [
        "/api/v1/research",
        "/api/v1/research/{research_id}/events",
        "/api/v1/documents/upload",
        "/api/v1/documents/{document_id}/reindex",
        "/api/v1/evaluations",
        "/api/v1/evaluations/experiments/compare",
        "/api/v1/health",
        "/api/v1/configuration",
    ]:
        assert p in paths
