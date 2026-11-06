FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/app/.cache/huggingface \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

# Capa de dependencias (se cachea mientras no cambie pyproject.toml).
ARG WITH_RAGAS=false
COPY pyproject.toml uv.lock* README.md ./
RUN mkdir -p src/ars && touch src/ars/__init__.py \
    && if [ "$WITH_RAGAS" = "true" ]; then uv sync --no-dev --extra ragas; else uv sync --no-dev; fi

COPY . .
RUN if [ "$WITH_RAGAS" = "true" ]; then uv sync --no-dev --extra ragas; else uv sync --no-dev; fi \
    && useradd --create-home --uid 1000 ars \
    && mkdir -p /app/storage /app/.cache && chown -R ars:ars /app/storage /app/.cache
USER ars

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"

CMD ["sh", "-c", "alembic upgrade head && uvicorn ars.api.main:app --host 0.0.0.0 --port 8000"]
