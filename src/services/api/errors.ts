export type ApiErrorKind =
  | 'network'
  | 'timeout'
  | 'aborted'
  | 'unauthorized'
  | 'not_found'
  | 'conflict'
  | 'validation'
  | 'budget'
  | 'server'
  | 'http'
  | 'contract';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly userMessage: string;

  constructor(
    kind: ApiErrorKind,
    userMessage: string,
    status?: number,
    options?: { cause?: unknown },
  ) {
    super(userMessage, options);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.userMessage = userMessage;
  }


  get retryable(): boolean {
    return (
      this.kind === 'network' ||
      this.kind === 'timeout' ||
      this.kind === 'server'
    );
  }
}

interface FastApiValidationItem {
  loc?: unknown[];
  msg?: string;
}


export function extractDetail(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = (detail as FastApiValidationItem[])
      .map((d) => {
        const field = Array.isArray(d.loc)
          ? d.loc.filter((p) => p !== 'body').join('.')
          : '';
        return [field, d.msg].filter(Boolean).join(': ');
      })
      .filter(Boolean);
    return parts.length ? parts.join('; ') : null;
  }
  return null;
}

export function errorFromResponse(status: number, body: unknown): ApiError {
  const detail = extractDetail(body);
  switch (true) {
    case status === 401:
      return new ApiError(
        'unauthorized',
        'El backend requiere una API key válida. Configúrala en Configuración → Conexión.',
        status,
      );
    case status === 402:
      return new ApiError(
        'budget',
        detail ?? 'Se agotó el presupuesto de tokens de la operación.',
        status,
      );
    case status === 404:
      return new ApiError(
        'not_found',
        detail ?? 'No se encontró el recurso solicitado.',
        status,
      );
    case status === 409:
      return new ApiError(
        'conflict',
        detail ?? 'La operación no es válida en el estado actual del recurso.',
        status,
      );
    case status === 413 || status === 422:
      return new ApiError(
        'validation',
        detail ?? 'Los datos enviados no son válidos.',
        status,
      );
    case status >= 500:
      return new ApiError(
        'server',
        'El servidor encontró un error al procesar la solicitud. Inténtalo de nuevo en unos instantes.',
        status,
      );
    default:
      return new ApiError(
        'http',
        detail ?? `La solicitud falló (HTTP ${status}).`,
        status,
      );
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

export function toUserMessage(e: unknown): string {
  if (isApiError(e)) return e.userMessage;
  return 'Ocurrió un error inesperado.';
}
