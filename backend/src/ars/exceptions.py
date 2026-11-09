class ARSError(Exception):
    """Base de las excepciones del dominio."""


class ConfigurationError(ARSError):
    pass


class NotFoundError(ARSError):
    pass


class ConflictError(ARSError):
    pass


class FileValidationError(ARSError):
    """El archivo subido no es válido."""


class ExtractionError(ARSError):
    pass


class LLMError(ARSError):
    """Fallo al llamar al modelo generativo o al interpretar su salida."""


class BudgetExceededError(ARSError):
    """Se alcanzó el presupuesto de tokens de la investigación."""


class EmbeddingDimensionError(ConfigurationError):
    pass
