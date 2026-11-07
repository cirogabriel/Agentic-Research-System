

## Arrancar

**Terminal 1: base de datos** (arranca primero)

```bash
cd ~/projects/agentic-research
docker compose -f backend/docker-compose.yml up db
```

Espera a ver `database system is ready to accept connections`.

**Terminal 2: backend**

Si usaste `uv`:

```bash
cd ~/projects/agentic-research/backend
uv run uvicorn ars.api.main:app --reload --port 8000
```

Espera a ver `Application startup complete`.

**Terminal 3: frontend**

```bash
cd ~/projects/agentic-research
npm run dev
```

Abre http://localhost:5173. El indicador superior debe decir "Todos los sistemas operativos".

## Comprobar que todo responde (opcional)

```bash
curl http://localhost:8000/api/v1/health
```

## Cuándo sí repetir algo

| Situación | Qué ejecutar |
|---|---|
| Hiciste `git pull` y hay migraciones nuevas | `alembic upgrade head` (o `uv run alembic upgrade head`) en `backend/`, antes de arrancar el backend |
| Cambiaste dependencias del backend | `pip install -e .` (o `uv sync`) en `backend/` |
| Cambiaste `package.json` | `npm install` en la raíz |
| Cambiaste `backend/.env` | Reinicia el backend (Ctrl + C y vuelve a lanzarlo) |

`alembic upgrade head` es seguro de ejecutar siempre: si no hay migraciones pendientes, no hace nada.

## Detener todo

```bash
# Terminales 3, 2 y 1: Ctrl + C en cada una, en ese orden
docker compose -f backend/docker-compose.yml down
```

`down` conserva tus documentos indexados y el historial. Para borrarlos también, usa `down -v`.

## Variante: base de datos en segundo plano

Si prefieres no ocupar una terminal con la base de datos:

```bash
docker compose -f backend/docker-compose.yml up -d db     # arrancar
docker compose -f backend/docker-compose.yml logs -f db  # ver logs (opcional)
docker compose -f backend/docker-compose.yml down         # detener
```

Con esto solo necesitas dos terminales: backend y frontend.