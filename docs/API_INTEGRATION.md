# Integración con la API (FastAPI)

Fuente de verdad: el código del backend (`src/ars/api/routes/*`, `src/ars/schemas/api.py`). Todos los contratos están en
`src/types/api.ts` y `src/types/events.ts` como **esquemas zod**; los tipos TypeScript se infieren de ellos y cada respuesta
se valida en `src/services/api/client.ts` (si el formato no coincide → `ApiError('contract')`).
Prefijo de todas las rutas: `/api/v1` (`VITE_API_BASE_URL`). Autenticación opcional: cabecera `X-API-Key` (excepto `/health`).

## Funcionalidad → endpoint

| Pantalla / acción | Servicio (`src/services`) | Endpoint | Datos clave |
|---|---|---|---|
| Nueva investigación / seguimiento | `researchService.create` | `POST /research` → 202 | `{query (5–4000), options?, parent_research_id?}` → `ResearchOut` |
| Listar (Historial, Mis investigaciones, Dashboard) | `researchService.list` | `GET /research?limit&offset&status` | `{items, total}` |
| Abrir investigación | `researchService.get` | `GET /research/{id}` | `ResearchOut` (incluye `parent_id`, `clarification_questions`, tokens, costo) |
| Tokens/costo en vivo, `error` | `researchService.status` | `GET /research/{id}/status` | `ResearchStatusOut` |
| Informe | `researchService.report` | `GET /research/{id}/report?format=json` | `ReportOut` (409 si aún no existe) |
| Descargar informe | `fetchReportMarkdown` | `GET /research/{id}/report?format=markdown` | `text/markdown` |
| Responder aclaraciones | `researchService.clarify` | `POST /research/{id}/clarifications` | `{answer}` |
| Reanudar | `researchService.resume` | `POST /research/{id}/resume` | 409 si no es reanudable |
| Progreso en tiempo real | `connectResearchEvents` | `GET /research/{id}/events` (SSE) | ver más abajo |
| Subir documento | `documentsService.upload` | `POST /documents/upload` (multipart `file`) | 202 (`created`/`updated`) o 200 (`duplicate`) |
| Listar / filtrar documentos | `documentsService.list` | `GET /documents?limit&offset&status&file_type` | `{items, total}` |
| Detalle / metadatos / fuentes | `documentsService.get` | `GET /documents/{id}` | `DocumentOut` |
| Eliminar | `documentsService.remove` | `DELETE /documents/{id}` → 204 | |
| Reindexar | `documentsService.reindex` | `POST /documents/{id}/reindex?force` | `reindexing` / `up_to_date` |
| Datasets | `evaluationsService.datasets/createDataset` | `GET/POST /evaluations/datasets` | `DatasetCreate` validado en cliente |
| Experimentos | `evaluationsService.list/create/get` | `GET/POST /evaluations`, `GET /evaluations/{id}` | `summary` + resultados por ítem |
| Comparación A/B/C | `evaluationsService.compare` | `GET /evaluations/experiments/compare?experiment_ids&dataset_id` | 409 si < 2 completados |
| Estado del backend | `systemService.health` | `GET /health` | `{status, version, checks}` |
| Configuración (solo lectura) | `systemService.configuration` | `GET /configuration` | diccionario sin secretos |

## Estados reales

- Investigación: `pending · running · completed · failed · needs_clarification · interrupted`.
- Documento: `processing · indexed · failed` (el backend **no** tiene un estado `uploaded`).
- Experimento: `pending · running · completed · failed`.

## Eventos SSE

Formato (`api/routes/research.py`): `id:` = id de fila (entero creciente), `event:` = tipo, `data:` = `{"type","message","payload","at"}`.
Al terminar emite `event: end` (sin id). Reanuda con la cabecera `Last-Event-ID`. Al conectar reenvía **todo el historial**, por lo que
el mismo flujo sirve para investigaciones en curso y finalizadas.

| Tipo | Payload usado por la UI | Efecto en la UI |
|---|---|---|
| `research.started` | – | Etapa *Comprensión* en curso |
| `query.analyzed` | – | *Comprensión* ✓, *Planificación* en curso, Supervisor trabajando |
| `research.needs_clarification` | `questions[]` | Muestra las preguntas y el formulario de respuesta |
| `plan.created` | `rationale`, `tasks[]` | *Planificación* ✓, Supervisor ✓, Research Agent en curso |
| `task.started` / `task.completed` | `task`, (`error`) | Contador de subtareas |
| `analysis.completed` | – | *Investigación*/*Análisis* ✓, Verification Agent en curso |
| `budget.exhausted` | – | Nota visible en el panel de agentes |
| `verification.completed` | cobertura (en `message`) | *Verificación* ✓, Supervisor decidiendo |
| `supervisor.decision` | `action` (`continue`/`finalize`) | `continue` → nueva iteración; `finalize` → Report Agent en curso |
| `report.generated` | – | *Generación del informe* ✓ |
| `research.completed` | – | Estado final; 100 % |
| `research.failed` | – | Estado de fallo (el texto de la excepción **no** se muestra) |

El backend no emite `analysis.started`; la fase de análisis se **infiere** cuando todas las subtareas de la iteración terminaron
(`features/research/progress.ts`, con pruebas). No se muestra ninguna actividad que no esté respaldada por un evento.

## Reconexión

`services/api/eventStream.ts` (`runEventStream`): ante una caída reconecta con backoff exponencial (1 s → 15 s, 6 intentos),
enviando `Last-Event-ID`; descarta ids ya entregados (sin duplicados) y distingue cierre normal (`end`) de cierre inesperado.
Errores 4xx (salvo 408/429) no se reintentan. Agotados los reintentos, el panel muestra «Reintentar conexión».
Se usa `fetch` + parser propio (`sse.ts`) y no `EventSource` porque este **no permite enviar `X-API-Key`**.

## Errores

`ApiError` normaliza: `network · timeout · aborted · unauthorized(401) · not_found(404) · conflict(409) · validation(413/422) · budget(402) · server(5xx) · contract`.
`{detail: string | [{loc,msg}]}` de FastAPI se convierte a texto legible. El cuerpo de un 5xx **nunca** se muestra.

## CORS

- **Docker / producción (recomendado):** nginx sirve la app y reenvía `/api` → sin CORS (`VITE_API_BASE_URL=/api/v1`).
- **Desarrollo con proxy de Vite:** `DEV_PROXY_TARGET=http://localhost:8000` y `VITE_API_BASE_URL=/api/v1` → sin CORS.
- **Origen distinto:** en el `.env` del backend, `CORS_ORIGINS=["http://localhost:5173"]` (lista JSON). El backend ya permite cualquier método y cabecera (incluye `X-API-Key` y `Last-Event-ID`).
