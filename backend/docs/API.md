# API REST (`/api/v1`)

Swagger: `/docs` · ReDoc: `/redoc` · OpenAPI: `/openapi.json`. Si `API_KEY` está definida, enviar `X-API-Key` (excepto `/health`).

Errores: `{"detail": "..."}` con 404 (no existe), 409 (conflicto de estado), 422 (validación o archivo inválido), 401 (API key), 402 (presupuesto), 500.

## Investigaciones

| Método | Ruta                            | Descripción                                                                           |
| ------ | ------------------------------- | ------------------------------------------------------------------------------------- |
| POST   | `/research`                     | Crea y lanza (202). Cuerpo: `query`, `options`, `parent_research_id?`                 |
| GET    | `/research`                     | Lista (`limit`, `offset`, `status`)                                                   |
| GET    | `/research/{id}`                | Detalle                                                                               |
| GET    | `/research/{id}/status`         | Estado, etapa, iteración, tokens, costo, error                                        |
| GET    | `/research/{id}/report`         | Informe (`?format=markdown` para texto) con fuentes y hallazgos; 409 si aún no existe |
| GET    | `/research/{id}/events`         | **SSE** (`Last-Event-ID` para reanudar); `?stream=false` devuelve JSON                |
| POST   | `/research/{id}/clarifications` | Responde a las aclaraciones solicitadas                                               |
| POST   | `/research/{id}/resume`         | Reanuda desde el último checkpoint (estados `interrupted`/`failed`)                   |

`options`: `max_iterations`, `token_budget`, `top_k`, `retrieval_strategy`, `query_transform`, `document_ids`, `parallel`, `reinvestigate`.

Estados: `pending → running → completed | failed | needs_clarification | interrupted`.

Eventos SSE (`event:` = tipo): `research.started`, `query.analyzed`, `plan.created`, `task.started`, `task.completed`, `analysis.completed`, `verification.completed`, `supervisor.decision`, `budget.exhausted`, `report.generated`, `research.completed`, `research.failed`, `research.needs_clarification`, y `end` (cierre del flujo).

```bash
curl -N http://localhost:8000/api/v1/research/$RID/events
# id: 7
# event: task.completed
# data: {"type":"task.completed","message":"Placas: 5 fragmento(s)","payload":{...},"at":"..."}
```

## Documentos

| Método | Ruta                      | Descripción                                                                                                                                                                                     |
| ------ | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| POST   | `/documents/upload`       | `multipart/form-data` (`file`). 202 y se indexa en segundo plano; **200** si el contenido ya existía (`action: duplicate`); mismo nombre con otro contenido → `action: updated` (nueva versión) |
| GET    | `/documents`              | Lista (`limit`, `offset`, `file_type`, `status`)                                                                                                                                                |
| GET    | `/documents/{id}`         | Metadatos y estado (`processing                                                                                                                                                                 | indexed | failed`) |
| DELETE | `/documents/{id}`         | Elimina documento, chunks y archivo                                                                                                                                                             |
| POST   | `/documents/{id}/reindex` | `?force=true` para forzar; `up_to_date` si no hay cambios                                                                                                                                       |

## Evaluación

| Método | Ruta                               | Descripción                                                |
| ------ | ---------------------------------- | ---------------------------------------------------------- |
| POST   | `/evaluations/datasets`            | Crea un dataset                                            |
| GET    | `/evaluations/datasets`            | Lista datasets                                             |
| POST   | `/evaluations`                     | Lanza un experimento (`mode`: `retrieval`, `A`, `B`, `C`)  |
| GET    | `/evaluations`                     | Lista                                                      |
| GET    | `/evaluations/{id}`                | Detalle con resultados por ítem                            |
| GET    | `/evaluations/experiments/compare` | Compara (`experiment_ids` o último A/B/C del `dataset_id`) |

## Sistema

`GET /health` (BD, pgvector, dimensión de embeddings, clave configurada, checkpointing) · `GET /configuration` (configuración efectiva **sin secretos**).

## Decisiones de diseño

Las operaciones largas devuelven 202 y se siguen por `/status` o SSE; nunca bloquean la petición. SSE se implementa leyendo la tabla `research_events` (orden por `id`), por lo que **sobrevive a reinicios** y permite reconexión con `Last-Event-ID`. `/evaluations/experiments/compare` se declara antes que `/{evaluation_id}` para que «experiments» no se interprete como UUID.
