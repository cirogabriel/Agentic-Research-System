# Arquitectura del frontend

## Principios
1. **El backend es la única fuente de verdad.** El frontend no implementa RAG, embeddings, LangGraph ni agentes; solo controla y visualiza.
2. **Sin datos simulados.** Todo dato visible sale de un endpoint; lo que no existe se omite o se deriva de forma explícita (ver `BACKEND_GAPS.md`).
3. **El diseño es la referencia visual.** `src/styles/globals.css` conserva las clases y tokens del ZIP de diseño (sidebar de 235/76 px, breakpoints 1100/820/520, paleta violeta, tipografía 10–12 px, burbujas con iconos de usuario/IA, panel oscuro de progreso). `app.css` añade solo lo que el diseño no cubría (tablas, formularios, modales, toasts…) con los mismos tokens.

## Capas

```
pages/ (rutas, composición)  →  features/<área>/ (componentes + queries + lógica pura)
                                   ↓                         ↓
                          components/ (UI común)      services/ (HTTP, un módulo por área)
                                                             ↓
                                                   services/api (cliente, errores, SSE)
```
- **`types/`**: esquemas zod = contratos del backend; los tipos se infieren (sin duplicados). `npm run gen:types` genera opcionalmente `openapi.generated.ts` desde `/openapi.json` para contrastar.
- **`services/api/`**: `client.ts` (base URL, timeout, `X-API-Key`, validación zod, normalización de errores), `sse.ts` (parser `text/event-stream` + conexión fetch), `eventStream.ts` (reconexión/deduplicación, sin React).
- **`features/*/queries.ts`**: hooks TanStack Query (claves centralizadas, sondeo condicional: investigaciones activas 4 s, documentos `processing` 3 s, experimentos activos 4 s).
- **`features/research/`**: `progress.ts` (eventos → etapas/agentes), `thread.ts` (hilos por `parent_id`), `reportUtils.ts` (secciones del informe y citas), `options.ts` (validación y construcción de `options`).
- **Estado global (zustand)**: `connectionStore` (API key en `sessionStorage`, aviso 401), `preferencesStore` (sidebar y valores por defecto de investigación, persistidos), `toastStore` (toasts + centro de notificaciones). El estado remoto vive solo en TanStack Query.
- **Rutas** (`app/router.tsx`): carga perezosa por página (recharts y react-markdown solo se descargan donde se usan).

## Decisiones

| Decisión | Motivo |
|---|---|
| `fetch` + parser SSE propio en vez de `EventSource` | `EventSource` no envía cabeceras (`X-API-Key`) y no controla la reconexión/`Last-Event-ID` |
| zod para contratos | Una sola definición para tipos y validación en tiempo de ejecución |
| Agentes y etapas derivados de eventos | No existe endpoint de ejecuciones; evita inventar actividad |
| Hilo por `parent_id` | El backend modela seguimientos como investigaciones enlazadas; solo se permite continuar una investigación `completed` (su informe es la memoria que usa el backend) |
| Markdown con `react-markdown` (sin HTML crudo) | Un informe generado por LLM no puede inyectar scripts |
| Citas `[S1]` → enlaces internos | Permiten saltar a la tarjeta de la fuente; los ids DOM son únicos por informe |
| API key solo en `sessionStorage` | Nunca en el bundle ni en `VITE_*`; las credenciales de OpenAI no existen en el frontend |
| Mensajes de error genéricos para fallos internos | No se exponen excepciones ni trazas (`research.failed`, 5xx, errores de experimentos) |
| nginx como proxy en producción | Misma-origen → sin CORS, SSE sin buffering, subidas grandes (`client_max_body_size`) |

## Estados de interfaz
Todas las listas pasan por `QueryBoundary`: *loading* (skeleton), *error* (mensaje comprensible + «Reintentar»), *empty* (explicación + acción) y contenido. Las mutaciones muestran toasts; los botones se deshabilitan durante `pending`; los estados `processing`/`running` se reflejan con insignias animadas.

## Accesibilidad
Navegación con `aria-current`, diálogos con `role="dialog"`/Escape/foco, regiones y `role="status"`/`alert`, filas clicables con `tabIndex` + Enter, barras de progreso con `role="progressbar"`, controles con etiquetas, `aria-live` en toasts y cola de subidas.

## Pruebas (Vitest + React Testing Library)
Lógica pura (parser SSE, reconexión sin duplicados, cliente HTTP/errores, derivación de progreso, hilos, informe, métricas, validaciones) y componentes con servicios simulados (envío de investigación, composer, mensajes, informe completo con tablas y citas, aclaraciones/fallos, carga/validación/borrado de documentos, estados de error, página de investigación con stream simulado, comparación de experimentos).
