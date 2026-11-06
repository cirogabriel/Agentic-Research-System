# Limitaciones del backend y modificaciones propuestas

El backend se entrega **sin modificar** (copia en `backend/`). Estas son las funcionalidades pedidas que no tienen soporte directo
en la API actual, cómo las resuelve el frontend sin inventar datos y qué cambio concreto las habilitaría.

| # | Necesidad | Estado actual | Solución en el frontend | Cambio propuesto en el backend |
|---|---|---|---|---|
| 1 | Actividad de agentes / tareas por investigación | Se guardan (`add_execution`) pero **no hay endpoint** | Se deriva únicamente de los eventos SSE | `GET /research/{id}/executions` → `[{agent, status, started_at, finished_at, tokens, error}]` |
| 2 | Historial de mensajes de la conversación | Existe tabla de mensajes, sin endpoint | Hilo = cadena `parent_id` (ancestros por `GET /research/{id}`, descendientes de la lista reciente) | `GET /research/{id}/thread` (ancestros + descendientes) y filtro `?parent_id=` en el listado |
| 3 | Búsqueda de texto en investigaciones/documentos | No hay parámetro `q` | Filtro cliente sobre la página cargada (se indica en la UI) | `?q=` (ILIKE sobre `query`, `filename`, `title`) |
| 4 | Métricas del dashboard (tokens totales, por periodo) | Solo `total` por estado en los listados | Conteos con `limit=1&status=…`; tokens/costo sumados sobre las últimas 100 investigaciones (rotulado) | `GET /stats` con agregados (totales por estado, tokens y costo, por día) |
| 5 | Resumen de cada investigación en el historial | El listado no incluye resumen | Se pide el informe al expandir una fila completada | Añadir `summary` (resumen ejecutivo) a `ResearchOut` |
| 6 | Metadatos de fuente (autor, título) | `SourceOut` solo trae `document_name`/`snippet` | Se completan con `GET /documents/{document_id}` (si el documento fue eliminado, se indica) | Añadir `title` y `author` a `SourceOut` |
| 7 | Fragmento original completo / visor | Solo `snippet` (≤1500 car.) | Se muestra el snippet guardado | `GET /documents/{id}/chunks?page=` |
| 8 | Modificar configuración desde la UI | `GET /configuration` es solo lectura; todo es variable de entorno | Panel «Solo lectura» + valores por defecto **por solicitud** (`options`), guardados en el navegador | Si se desea: `PATCH /configuration` restringido a claves seguras (con autenticación) |
| 9 | Error en `ResearchOut` | Solo en `/status` | Se usa un mensaje genérico (no se muestran excepciones) | — |
| 10 | Progreso de subida y estado `uploaded` | `fetch` no da progreso; no hay estado `uploaded` | Indicador por archivo (subiendo/enviado) y sondeo hasta `indexed` | — |
| 11 | Sidebar del diseño: «Fuentes», «Colecciones», «Métricas» | Sin endpoints equivalentes | Se omiten (Métricas → *Evaluaciones*; fuentes → dentro de cada informe) | `GET /sources` y `/collections` si se quieren esas vistas |
| 12 | Usuario / perfil / tema | No hay autenticación de usuarios | El chip de perfil muestra el backend conectado; se omite el selector de tema (el diseño no define modo oscuro) | — |

Aviso de costo: lanzar investigaciones o experimentos (modos A/B/C, RAGAS) consume tokens del LLM **del backend**; la UI pide confirmación explícita en los experimentos.
