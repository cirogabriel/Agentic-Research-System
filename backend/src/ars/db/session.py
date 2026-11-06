from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ars.config import Settings
from ars.exceptions import EmbeddingDimensionError


def make_engine(settings: Settings) -> Engine:
    return create_engine(settings.database_url, pool_size=settings.db_pool_size, pool_pre_ping=True, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: los objetos siguen siendo legibles tras el commit (los servicios los convierten a DTO).
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Una transacción por bloque: commit al salir, rollback ante cualquier excepción."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping(factory: sessionmaker[Session]) -> bool:
    try:
        with session_scope(factory) as s:
            s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def vector_extension_installed(factory: sessionmaker[Session]) -> bool:
    with session_scope(factory) as s:
        return s.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first() is not None


def check_vector_dimension(factory: sessionmaker[Session], expected: int) -> None:
    """Falla pronto y con un mensaje claro si EMBEDDING_DIMENSIONS no coincide con la columna real."""
    with session_scope(factory) as s:
        row = s.execute(
            text(
                "SELECT a.atttypmod FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.relname = 'document_chunks' AND a.attname = 'embedding'"
            )
        ).first()
    if row is not None and row[0] != expected:
        raise EmbeddingDimensionError(
            f"La columna document_chunks.embedding tiene dimensión {row[0]} pero EMBEDDING_DIMENSIONS={expected}. "
            "Cambia el modelo/dimensión solo junto con una nueva migración y una reindexación completa."
        )
