# Agentic Research System · Frontend

Cliente web (React 19 + TypeScript estricto + Vite + Tailwind 4) del backend **Agentic Research System** (FastAPI · LangGraph · pgvector).
Sigue el diseño visual entregado y se comunica **solo** con endpoints reales del backend. No contiene lógica de IA ni credenciales de OpenAI.

## Funcionalidades
- **Investigación conversacional**: nueva investigación, seguimiento con memoria (`parent_research_id`), aclaraciones, reanudar, informe final (resumen, hallazgos verificados, conclusiones, fuentes con fragmento, Markdown completo, copiar/descargar).
- **Progreso en tiempo real (SSE)** con reconexión: etapas y actividad de los 5 agentes derivadas de los eventos reales.
- **Documentos**: arrastrar y soltar, validación de formato/tamaño, estados `processing/indexed/failed`, filtros, paginación, detalle, reindexar, eliminar.
- **Historial / Mis investigaciones / Dashboard** con datos reales.
- **Evaluaciones y Experimentos**: lanzar, consultar métricas de recuperación, generación, agentes y rendimiento, comparar A/B/C.
- **Configuración**: parámetros del backend (solo lectura) y valores por defecto por solicitud (modificables), API key, estado de conexión.
- **Modelos y consumo** (tokens y costo de tus investigaciones).

Qué no se puede hacer con la API actual y cómo se resolvió: [`docs/BACKEND_GAPS.md`](docs/BACKEND_GAPS.md).

## Estructura
```
src/
  app/          router (lazy), providers, layouts (AppLayout: sidebar/topbar), nav
  components/   ui/ (Button) · common/ (estados, modal, toasts, paginación, markdown)
  features/     research · documents · evaluations · history · settings (componentes + queries + lógica pura)
  pages/        una por ruta
  services/     api/ (client, errors, sse, eventStream) + research/documents/evaluations/system
  stores/       zustand: conexión, preferencias, toasts
  types/        contratos zod del backend + eventos
  utils/        formato, cn
  styles/       globals.css (diseño original) + app.css
docs/           API_INTEGRATION.md · FRONTEND_ARCHITECTURE.md · BACKEND_GAPS.md
backend/        copia SIN MODIFICAR del backend entregado (para docker compose integrado)
```

## Requisitos
Node 20+ (probado con 22) y el backend corriendo (o Docker).

## Variables de entorno (`.env.example`)
| Variable | Descripción |
|---|---|
| `VITE_API_BASE_URL` | URL base de la API incluyendo `/api/v1` (`http://localhost:8000/api/v1` o `/api/v1` detrás de nginx/proxy) |
| `VITE_API_TIMEOUT_MS` | Timeout de peticiones normales (30000). El stream SSE no lo usa |
| `DEV_PROXY_TARGET` | Solo `npm run dev`: proxy de Vite hacia el backend (evita CORS) |

La **API key del backend** (si `API_KEY` está definida allí) se introduce en *Configuración → Conexión*; se guarda en `sessionStorage`.

## Ejecución local
```bash
# 1) Backend (en su carpeta): ver backend/README.md  → http://localhost:8000
# 2) Frontend
cp .env.example .env
npm install
npm run dev        # http://localhost:5173
```
CORS: o bien `DEV_PROXY_TARGET=http://localhost:8000` + `VITE_API_BASE_URL=/api/v1` en `.env` (sin CORS), o bien en el `.env` **del backend** `CORS_ORIGINS=["http://localhost:5173"]`.

## Docker
```bash
# Frontend + backend + Postgres/pgvector
cp backend/.env.example backend/.env      # completa OPENAI_API_KEY (solo en el backend)
docker compose up --build                 # → http://localhost:8080  (nginx sirve la app y reenvía /api al backend)

# Solo frontend en desarrollo contra un backend local en :8000
docker compose -f docker-compose.dev.yml up --build     # → http://localhost:5173

# Solo la imagen de producción del frontend
docker build -t ars-frontend .
docker run -p 8080:80 -e BACKEND_URL=http://host.docker.internal:8000 ars-frontend
```
Para apuntar a otro origen sin proxy: `--build-arg VITE_API_BASE_URL=https://api.ejemplo.com/api/v1` (requiere `CORS_ORIGINS` en el backend).

## Scripts
`npm run dev` · `npm run build` · `npm run preview` · `npm run typecheck` · `npm test` · `npm run gen:types` (opcional, requiere backend en :8000)

## Pruebas
```bash
npm test
```
Vitest + React Testing Library con servicios simulados (nunca llaman a OpenAI ni al backend). Cobertura temática en `docs/FRONTEND_ARCHITECTURE.md`.

## Estado de verificación (honesto)
Verificado en el entorno de generación: `tsc` (strict) sin errores, **76 pruebas Vitest en verde** y `vite build` correcto.
**No verificado:** la integración extremo a extremo contra el backend real (no se ejecutó ni se contactó con él ni con OpenAI), el aspecto visual en un navegador, ni la compilación de las imágenes Docker. Esas comprobaciones quedan para tu primera ejecución; si algún contrato difiere, el cliente lo reportará como «formato inesperado» (validación zod).

## Seguridad
Sin claves de OpenAI en el cliente. API key opcional en `sessionStorage`. Markdown sin HTML crudo. Errores 5xx y excepciones del backend nunca se muestran. Los experimentos que consumen LLM exigen confirmación.
