# Control de costos y tokens

Prioridad del proyecto: calidad **sin** consumo descontrolado. Las medidas, con dónde viven:

| # | Medida | Implementación |
|---|---|---|
| 1 | Un único modelo generativo configurable | `LLMGateway` + `LLM_MODEL` |
| 2 | Reutilización de resultados entre agentes | Etiquetas `S#` compartidas, `findings` acumulativos, caché de retrieval |
| 3 | Presupuesto de tokens por investigación | `UsageTracker` (`TOKEN_BUDGET`); `check()` antes de cada llamada |
| 4 | Reserva para el informe | `REPORT_RESERVE_RATIO` (20 %): el trabajo normal no la toca |
| 5 | Límite de iteraciones y subtareas | `MAX_ITERATIONS`, `MAX_SUBTASKS`, `MAX_FOLLOWUP_TASKS` |
| 6 | Paralelismo solo si ayuda | Subtareas independientes (`Send`); opción `parallel` |
| 7 | Recuperar antes de generar | El LLM solo ve fragmentos seleccionados |
| 8 | Truncado inteligente del contexto | `select_evidence`: reparto round‑robin de `ANALYSIS_MAX_EVIDENCE_CHARS` entre subtareas; fragmentos de ≤900–1500 car. en prompts |
| 9 | Caché de embeddings | Tabla `embedding_cache` + caché de consultas |
| 10 | Caché de recuperación | `TTLCache` invalidada al cambiar documentos |
| 11 | Lotes | Embeddings por lotes; una llamada de verificación para todos los casos dudosos |
| 12 | Salidas compactas y limitadas | Esquemas Pydantic + `max_tokens` por llamada (120–1500) |
| 13 | Evitar llamadas innecesarias | Ver tabla siguiente |
| 14 | Registro de consumo | `research_sessions.tokens_*`, `cost_usd`, `agent_executions` por agente |

## Dónde se evita el LLM
| Situación | Sin LLM |
|---|---|
| Consulta bien formada | Query Processor heurístico |
| Pregunta simple | Plan de 1 subtarea |
| Decisión de continuar/parar | Reglas sobre datos estructurados |
| Elegir estrategia de búsqueda | Router determinista |
| Hechos con alto solapamiento léxico | Verificados por código |
| Sin evidencia recuperada | No se llama al análisis |
| Referencias, clasificación, metodología | Generadas por el renderizador |
| Presupuesto agotado | Informe determinista degradado |

## Estimación de costo
`cost_usd = (tokens_in·P_in + tokens_out·P_out + tokens_embedding·P_emb) / 1e6`, con los precios de `.env`. El de embeddings se estima (~4 car./token) porque la API no lo devuelve por lote. **Es una estimación**, no una factura.

## Orden de magnitud por investigación (estimado, no medido)
Una investigación típica hace ~4–6 llamadas al LLM (plan, análisis, verificación opcional, informe; más una por iteración extra). Con límites por defecto, el máximo teórico lo marca `TOKEN_BUDGET` (60 000 tokens). Mide el valor real con tus documentos usando los experimentos A/B/C (`cost.*`).

## Consejos
Baja `EVIDENCE_PER_TASK`/`RETRIEVAL_TOP_K` si el contexto es grande; mantén `rerank` activado (es local y gratis) para poder usar `top_k` pequeños; activa `multi_query`/`HyDE` solo si el dataset demuestra una mejora.
