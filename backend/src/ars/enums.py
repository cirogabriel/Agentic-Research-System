from enum import StrEnum


class ResearchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_CLARIFICATION = "needs_clarification"
    INTERRUPTED = "interrupted"

    @classmethod
    def terminal(cls) -> set[str]:
        return {cls.COMPLETED, cls.FAILED, cls.NEEDS_CLARIFICATION, cls.INTERRUPTED}


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Support(StrEnum):
    """Resultado de la verificación de un hallazgo contra sus fuentes."""

    SUPPORTED = "supported"
    PARTIAL = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"  # no se pudo verificar (p. ej. presupuesto agotado)


class ExperimentMode(StrEnum):
    RETRIEVAL = "retrieval"  # solo métricas de recuperación
    A = "A"  # RAG convencional sin agentes
    B = "B"  # Supervisor + agentes, secuencial, sin ciclo de verificación
    C = "C"  # Supervisor + agentes, paralelo y con ciclo de verificación
