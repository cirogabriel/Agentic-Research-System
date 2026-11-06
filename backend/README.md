# Agentic Research System

Backend de **investigación inteligente multiagente**: recibe preguntas complejas, planifica la investigación, la reparte entre agentes especializados, recupera evidencias de tus documentos con RAG, las analiza y verifica, y entrega un **informe estructurado con referencias**. Incluye evaluación automática para medir si la arquitectura multiagente realmente mejora a un RAG convencional, y cuánto cuesta esa mejora.

> **Estado de la entrega.** El código fue escrito y revisado **estáticamente** (sintaxis, imports entre módulos, coherencia de nombres, resolución de dependencias con `uv pip compile`). **No se ejecutó el proyecto ni sus pruebas**, no se probó contra PostgreSQL ni contra OpenAI. Es de esperar algún ajuste menor en la primera ejecución; ver [«Qué no está verificado»](#qué-no-está-verificado).

## 1. Qué problema resuelve

Un chatbot con documentos responde con un único ciclo «buscar → generar». Una pregunta como *«Investiga las causas geológicas de los terremotos en los Andes, compara las explicaciones y cita las fuentes»* tiene varios aspectos, puede requerir varias búsquedas, y sus afirmaciones deben comprobarse contra la evidencia. Este sistema modela ese proceso: **planifica → delega → recupera → analiza → verifica → decide si investigar más → redacta**, con límites explícitos de iteraciones y de tokens.

## 2. Arquitectura en una imagen

```mermaid
flowchart LR
    Client([Cliente]) -->|REST + SSE| API[FastAPI]
    API -->|202 + tarea en 2º plano| RUN[BackgroundRunner]
    RUN --> G[[Grafo LangGraph<br/>Supervisor–Worker]]
    G --> RAG[Servicios RAG<br/>router · transformaciones · RRF · reranker]
    G --> LLM[LLMGateway<br/>un solo modelo · presupuesto]
    RAG --> PG[(PostgreSQL + pgvector)]
    G -->|checkpoints + resultados + eventos| PG
    G -. opcional .-> MCP[Servidores MCP<br/>documentos · recuperación · evaluación]
    MCP --> RAG
    API --> EVAL[Evaluación A/B/C] --> PG
```

Detalles en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 3. Tecnologías

Python 3.11+ · FastAPI · LangChain (`langchain-core`, `langchain-openai`, `langchain-text-splitters`) · LangGraph (+ checkpointer PostgreSQL) · OpenAI (generación y embeddings) · PostgreSQL + pgvector · SQLAlchemy 2.0 · Alembic · Pydantic v2 · Sentence-Transformers (cross-encoder) · Ragas (opcional) · MCP Python SDK · Docker Compose · uv · Pytest.

No se usan Redis, Celery, Kafka ni microservicios por agente: el trabajo es de E/S y el estado ya es durable en PostgreSQL (ver decisiones en la arquitectura).

## 4. Estructura de carpetas

```
src/ars/
├── config.py, logging_config.py, exceptions.py, enums.py, security.py, storage.py, runtime.py
├── api/            # FastAPI: main.py, deps.py, routes/{research,documents,evaluations,system}.py
├── db/             # models.py (SQLAlchemy 2.0), session.py
├── repositories/   # acceso a datos: documents (+chunks y búsquedas), research, evaluation
├── schemas/        # DTOs de la API, contratos de agentes, tipos RAG, consulta
├── llm/            # LLMGateway (salidas estructuradas), UsageTracker (presupuesto)
├── rag/            # validation, loaders, cleaning, chunking, embeddings, ingestion,
│                   # routing, query_transform, retrieval (RRF), reranker, cache
├── query/          # QueryProcessor (comprensión y normalización de consultas)
├── agents/         # supervisor, research, analysis, verification, report (+ render, toolbox, evidence)
├── graph/          # state, nodes, builder (StateGraph), runner, reporter, context (trim/filter)
├── services/       # documents, research, evaluation (casos de uso)
├── evaluation/     # métricas de recuperación/generación/agentes, experimentos A/B/C, Ragas
├── mcp_servers/    # document_server, retrieval_server, evaluation_server, client
└── tasks/          # BackgroundRunner
alembic/            # migración 0001
tests/              # unit, rag, agents, graph, api, evaluation, persistence (integración)
data/               # documentos de ejemplo y dataset de evaluación
docs/               # documentación técnica
scripts/            # init_db.sql, seed_sample_data.py
```

## 5. Responsabilidades por módulo (resumen)

| Módulo | Responsabilidad |
|---|---|
| `api` | Contrato HTTP, validación, códigos de estado, SSE. Sin lógica de negocio. |
| `services` | Casos de uso: orquestan repositorios, RAG y grafo. |
| `graph` | Define el flujo (nodos, aristas, estado) y la ejecución de una investigación. |
| `agents` | Lógica de cada agente; no conocen LangGraph (se pueden probar solos). |
| `rag` | Todo lo relativo a indexar y recuperar. |
| `llm` | Única salida hacia OpenAI generativo + control de tokens/costo. |
| `repositories`/`db` | SQL y modelo relacional. |
| `evaluation` | Métricas puras y ejecución de experimentos. |
| `mcp_servers` | Exposición de herramientas por MCP. |

## 6. Flujo completo de una investigación

```mermaid
flowchart TD
    A[POST /research] --> B[understand<br/>Query Processor]
    B -->|ambigua| Z1[needs_clarification]
    B -->|no requiere investigación| Z2[respuesta directa]
    B --> C[plan<br/>Supervisor]
    C -->|Send × N| D1[research_worker 1]
    C -->|Send × N| D2[research_worker N]
    D1 --> E[analyze<br/>Analysis Agent]
    D2 --> E
    E --> F[verify<br/>Verification Agent]
    F --> G[decide<br/>Supervisor]
    G -->|insuficiente y quedan iteraciones/tokens| D1
    G -->|suficiente / límite| H[report<br/>Report Agent]
    H --> I[final_evaluation] --> J[(Persistencia + SSE)]
```

1. La API crea la investigación (`pending`) y responde `202` de inmediato.
2. Un hilo de segundo plano ejecuta el grafo; cada paso emite eventos (SSE) y actualiza etapa y tokens.
3. Al terminar, el estado final se guarda en tablas relacionales (tareas, fuentes, hallazgos, informe).

## 7. Los agentes

| Agente | Qué hace | ¿Usa LLM? |
|---|---|---|
| Query Processor | Normaliza, detecta ambigüedad, extrae entidades/restricciones | Solo si la consulta no está clara |
| Supervisor | Planifica subtareas; decide continuar/finalizar | Plan: sí (omitido si es simple). Decisión: reglas deterministas |
| Research | Recupera evidencias con el pipeline RAG | No (indirectamente, si el router transforma la consulta) |
| Analysis | Hallazgos citados, coincidencias, contradicciones, vacíos | 1 llamada por iteración |
| Verification | Comprueba que cada afirmación esté en el fragmento citado | Solo para casos dudosos, en lote |
| Report | Redacta la narrativa; referencias y clasificación las genera el código | 1 llamada |

Más en [docs/AGENTS.md](docs/AGENTS.md) y [docs/LANGGRAPH.md](docs/LANGGRAPH.md).

## 8. Pipeline de indexación y recuperación

Indexación: **validar → extraer → limpiar → dividir → embeber por lotes → guardar (atómico) → metadatos/versión/hash**. Recuperación: **router → (rewrite | multi-query | RAG-Fusion | HyDE) → vectorial / léxica / híbrida (RRF) → reranking con cross-encoder → top-k**. Ver [docs/RAG.md](docs/RAG.md).

## 9. MCP

Tres servidores independientes (documentos, recuperación, evaluación) con el SDK oficial. Los agentes usan servicios Python directamente por defecto; con `AGENT_TOOL_TRANSPORT=mcp` el Research Agent consume el servidor MCP de recuperación. Ver [docs/MCP.md](docs/MCP.md).

## 10. Evaluación automática

Métricas de recuperación (Recall@K, Precision@K, MRR, NDCG@K, latencia), generación (deterministas + Ragas opcional), agentes (tasa de completitud, selección de herramientas, delegación, precisión de citas, cobertura, iteraciones, fallos, tokens, latencia) y experimentos A/B/C comparables. Ver [docs/EVALUATION.md](docs/EVALUATION.md).

## 11. Configuración de OpenAI

1. Crea una clave en <https://platform.openai.com/api-keys>.
2. Colócala **solo** en `.env` (`OPENAI_API_KEY=...`). Nunca en el código ni en git.
3. `LLM_MODEL` define el **único** modelo generativo de todos los agentes (por defecto `gpt-4o-mini`). `EMBEDDING_MODEL` es independiente (`text-embedding-3-small`, 1536 dim).
4. Los precios (`LLM_PRICE_*`) sirven solo para **estimar** costos; actualízalos según tu modelo.
5. Si cambias de modelo, revisa que acepte `temperature` y salidas por *function calling*.

## 12. Variables de entorno

Todas están comentadas en [`.env.example`](.env.example). Las más importantes:

| Variable | Descripción | Por defecto |
|---|---|---|
| `OPENAI_API_KEY` | Clave de OpenAI | — |
| `LLM_MODEL` / `EMBEDDING_MODEL` | Modelos generativo y de embeddings | `gpt-4o-mini` / `text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | Debe coincidir con la columna `vector(N)` | `1536` |
| `DATABASE_URL` | PostgreSQL (SQLAlchemy + psycopg 3) | `postgresql+psycopg://ars:ars@localhost:5432/ars` |
| `TOKEN_BUDGET` | Tokens (entrada+salida) por investigación | `60000` |
| `MAX_ITERATIONS`, `MAX_SUBTASKS` | Límites del Supervisor | `3`, `4` |
| `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHUNK_STRATEGY` | Chunking | `1000`, `150`, `recursive` |
| `RETRIEVAL_STRATEGY`, `QUERY_TRANSFORM` | `auto` = el router decide | `auto` |
| `RERANK_ENABLED`, `RERANK_MODEL` | Cross-encoder local | `true`, `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| `HYDE_ENABLED` | HyDE (experimental, costoso) | `false` |
| `API_KEY` | Si se define, exige `X-API-Key` | vacío (sin auth) |

## 13. Instalación y ejecución

### Con Docker Compose (recomendado)

```bash
cp .env.example .env          # edita OPENAI_API_KEY
docker compose up --build     # db (pgvector) + api; aplica migraciones al arrancar
# Swagger:  http://localhost:8000/docs      Salud: http://localhost:8000/api/v1/health
```

Ragas es opcional: `WITH_RAGAS=true docker compose up --build`.
Servidores MCP por HTTP: `docker compose --profile mcp up`.

### En local

```bash
docker compose up -d db                      # solo la base de datos
cp .env.example .env                         # DATABASE_URL con host localhost
uv sync                                      # o: uv sync --extra ragas
uv run alembic upgrade head
uv run uvicorn ars.api.main:app --reload
uv run python scripts/seed_sample_data.py    # indexa data/sample_docs y carga el dataset de ejemplo
```

La primera recuperación con reranking descarga el cross-encoder (~90 MB) desde Hugging Face.

## 14. Pruebas

```bash
uv sync --group dev
uv run pytest                                # unitarias, RAG, agentes, grafo, API, evaluación (sin OpenAI ni BD)
TEST_DATABASE_URL=postgresql+psycopg://ars:ars@localhost:5432/ars_test uv run pytest -m integration   # con PostgreSQL
```

Las pruebas usan dobles (`tests/fakes.py`): un LLM simulado, una recuperación en memoria y embeddings deterministas. **Ninguna consume créditos de OpenAI.**

## 15. Ejemplos de uso de la API

```bash
# 1) Subir documentos (202: se indexan en segundo plano; un duplicado devuelve 200 sin reprocesar)
curl -F "file=@data/sample_docs/andes_subduction.md" http://localhost:8000/api/v1/documents/upload

# 2) Lanzar una investigación
curl -X POST http://localhost:8000/api/v1/research -H "Content-Type: application/json" -d '{
  "query": "Investiga por qué se producen los terremotos en los Andes y qué placas están involucradas",
  "options": {"max_iterations": 2, "token_budget": 40000}
}'
# → {"id": "<RID>", "status": "pending", ...}

# 3) Seguir el progreso (SSE) o consultar el estado
curl -N http://localhost:8000/api/v1/research/<RID>/events
curl http://localhost:8000/api/v1/research/<RID>/status

# 4) Obtener el informe (JSON o Markdown)
curl "http://localhost:8000/api/v1/research/<RID>/report?format=markdown"

# 5) Evaluación: crear dataset → comparar A/B/C
curl -X POST http://localhost:8000/api/v1/evaluations/datasets -H "Content-Type: application/json" -d @data/evaluation/sample_retrieval_dataset.json
curl -X POST http://localhost:8000/api/v1/evaluations -H "Content-Type: application/json" -d '{"name":"A","dataset_id":"<DS>","mode":"A"}'
curl -X POST http://localhost:8000/api/v1/evaluations -H "Content-Type: application/json" -d '{"name":"C","dataset_id":"<DS>","mode":"C"}'
curl "http://localhost:8000/api/v1/evaluations/experiments/compare?dataset_id=<DS>"
```

Referencia completa en [docs/API.md](docs/API.md).

## 16. Qué no está verificado

Honestidad sobre el alcance de la revisión:

- **No se ejecutó nada**: ni la aplicación, ni las migraciones, ni las pruebas, ni llamadas a OpenAI/PostgreSQL. Las pruebas están escritas pero **no se han corrido**.
- Sí se hizo: compilación de todos los `.py`, análisis con `pyflakes` (sin nombres indefinidos), verificación de que cada import interno apunta a un nombre existente y de que no hay ciclos de importación, `uv pip compile` (resolución correcta, también con el extra `ragas`) y comprobación de que las APIs de LangChain/LangGraph/MCP/Ragas que se usan existen en las versiones resueltas.
- Las versiones resueltas son recientes (p. ej. langgraph 1.2, mcp 1.30); si alguna firma cambió en un detalle, el fallo aparecerá en la primera ejecución. Los puntos con más riesgo: **Ragas** (API cambiante, aislada en `evaluation/ragas_runner.py`), **`PostgresSaver`** (requisitos del pool) y **las salidas estructuradas** con tu modelo concreto.
- La verificación semántica (hechos respaldados) y el router usan heurísticas que conviene calibrar con tus documentos. La verificación léxica funciona mejor cuando consulta y documentos comparten idioma.
- No hay autenticación de usuarios (solo `API_KEY` opcional) ni ejecución distribuida: es un backend local/monoproceso por diseño.
- Extensiones futuras documentadas (no implementadas): RAPTOR, MultiVectorRetriever, ColBERT, OCR para PDF escaneados, `hnsw.iterative_scan` para filtros muy selectivos.
