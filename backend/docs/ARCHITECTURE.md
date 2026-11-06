# Arquitectura

## Vista general

```mermaid
flowchart TB
    subgraph Entrada
      C([Cliente HTTP]) --> R[Routers FastAPI]
    end
    R --> S[Services<br/>research · documents · evaluation]
    S --> BG[BackgroundRunner<br/>ThreadPoolExecutor]
    BG --> GR[graph.runner.run_research]
    GR --> SG[[StateGraph]]
    SG --> AG[agents/*]
    AG --> TB[Toolbox<br/>Direct | MCP]
    TB --> RS[RetrievalService]
    AG --> GW[LLMGateway + UsageTracker]
    RS --> EM[EmbeddingService<br/>lotes + caché]
    RS --> RR[Cross-Encoder local]
    RS --> DB[(PostgreSQL + pgvector)]
    S --> DB
    SG -. checkpoints .-> DB
    GW --> OAI[(OpenAI)]
    EM --> OAI
```

## Capas y dependencias (solo hacia abajo)

`api → services → (graph, rag, evaluation, repositories) → (agents, llm, db)`. Los agentes **no** importan LangGraph ni FastAPI; el grafo solo los conecta. No hay ciclos de importación a nivel de módulo (comprobado estáticamente); `runtime.AppContainer` es la raíz de composición y las dependencias circulares de tipos se resuelven con `TYPE_CHECKING`.

## Decisiones importantes y por qué

| Decisión | Motivo |
|---|---|
| **Supervisor–Worker** con `Send` | Es el patrón más simple que permite delegar y paralelizar; sin Swarm ni jerarquías extra. |
| **Agentes como clases Python puras** | Se prueban sin grafo ni LLM real; el grafo solo define el flujo. |
| **Un único `LLMGateway`** | Un modelo para todo, una sola contabilidad de tokens, un único punto para reintentos/timeouts. |
| **Salidas estructuradas (function calling)** | Decisiones verificables por esquema; admite valores por defecto, a diferencia del modo estricto. |
| **Decisiones con reglas, LLM solo si aporta** | `decide`, el router, la verificación obvia y la planificación simple no gastan tokens. |
| **Hilos en vez de Celery/Redis** | El trabajo es E/S; el estado es durable en PostgreSQL (sesión, eventos, checkpoints). Tras un reinicio las investigaciones quedan `interrupted` y se reanudan con `POST /research/{id}/resume`. |
| **Servicios Python internos + MCP opcional** | MCP aporta interoperabilidad, no se usa en cada llamada interna (latencia). |
| **pgvector + FTS en la misma BD** | Un único almacén transaccional; búsqueda híbrida sin otro servicio. |
| **Sesiones SQLAlchemy sincrónicas** | LangGraph y los agentes son síncronos (hilos); las rutas usan `run_in_threadpool`. |
| **Informe: narrativa por LLM, evidencias por código** | Referencias, clasificación y metodología deterministas → no se pueden «inventar». |
| **Tablas `Source` con `document_name` copiado** | El informe sigue siendo legible si se borra el documento (`document_id` pasa a NULL). Es una duplicación deliberada y acotada. |

## Persistencia de una investigación

Tres niveles diferentes (ver [LANGGRAPH.md](LANGGRAPH.md)): **memoria de ejecución** (estado del grafo + checkpoints), **persistencia de resultados** (tablas relacionales) e **historial conversacional** (`research_messages`, seguimientos con `parent_research_id`).

## Concurrencia

Cada investigación corre en un hilo del pool (`BACKGROUND_WORKERS`). Dentro del grafo, los workers de una iteración corren en paralelo (`max_concurrency = MAX_PARALLEL_WORKERS`). Los contadores de tokens están protegidos con un `Lock`.

## Seguridad

Validación de archivos por firma real, límites de tamaño/páginas/descompresión, rutas de almacenamiento a prueba de *path traversal*, HTML sin scripts, contenido recuperado envuelto en `<evidence>` con etiquetas estructurales neutralizadas, aviso explícito en los prompts, detección de patrones de prompt-injection (se registran y marcan, no se obedecen), herramientas cerradas por agente (sin ejecución de código), secretos solo por entorno y redacción de secretos en los logs. Ninguna medida es infalible: ver limitaciones en el README.
