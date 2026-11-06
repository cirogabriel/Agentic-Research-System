import type { ZodType } from 'zod'
import { ApiError, errorFromResponse } from './errors'

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'

export const apiConfig = {
  /** Sin barra final. Ej.: http://localhost:8000/api/v1 o /api/v1 (detrás de nginx). */
  baseUrl: rawBase.replace(/\/+$/, ''),
  timeoutMs: Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 30000) || 30000,
}

interface ClientHooks {
  getApiKey: () => string | null
  onUnauthorized: () => void
}
let hooks: ClientHooks = { getApiKey: () => null, onUnauthorized: () => {} }

/** Conecta el cliente con el estado de la app sin crear dependencias circulares. */
export function configureApiClient(next: Partial<ClientHooks>): void {
  hooks = { ...hooks, ...next }
}

export type QueryValue = string | number | boolean | null | undefined | readonly (string | number)[]

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, String(v)))
    else qs.append(key, String(value))
  }
  const suffix = qs.toString()
  return `${apiConfig.baseUrl}${path}${suffix ? `?${suffix}` : ''}`
}

export function authHeaders(): Record<string, string> {
  const key = hooks.getApiKey()
  return key ? { 'X-API-Key': key } : {}
}

export interface RequestOptions<T> {
  method?: 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH'
  query?: Record<string, QueryValue>
  json?: unknown
  formData?: FormData
  /** Si se indica, la respuesta se valida contra el esquema (error `contract` si no coincide). */
  schema?: ZodType<T>
  signal?: AbortSignal
  timeoutMs?: number
  as?: 'json' | 'text' | 'none'
  fetchImpl?: typeof fetch
}

async function safeJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return null
  }
}

export async function request<T = unknown>(path: string, opts: RequestOptions<T> = {}): Promise<T> {
  const { method = 'GET', query, json, formData, schema, signal, timeoutMs = apiConfig.timeoutMs, as = 'json' } = opts
  const doFetch = opts.fetchImpl ?? fetch
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const onAbort = () => controller.abort()
  signal?.addEventListener('abort', onAbort)

  const headers: Record<string, string> = { Accept: as === 'text' ? 'text/markdown, text/plain' : 'application/json', ...authHeaders() }
  let body: BodyInit | undefined
  if (formData) body = formData // el navegador fija el boundary multipart
  else if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  }

  let res: Response
  try {
    res = await doFetch(buildUrl(path, query), { method, headers, body, signal: controller.signal })
  } catch (cause) {
    if (timedOut) throw new ApiError('timeout', 'El servidor tardó demasiado en responder.', undefined, { cause })
    if (signal?.aborted) throw new ApiError('aborted', 'La solicitud fue cancelada.', undefined, { cause })
    throw new ApiError('network', 'No se pudo conectar con el backend. Verifica que esté en ejecución y que la URL y CORS estén configurados.', undefined, { cause })
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onAbort)
  }

  if (!res.ok) {
    const err = errorFromResponse(res.status, await safeJson(res))
    if (err.kind === 'unauthorized') hooks.onUnauthorized()
    throw err
  }
  if (as === 'none' || res.status === 204) return undefined as T
  if (as === 'text') return (await res.text()) as T

  const data: unknown = await safeJson(res)
  if (!schema) return data as T
  const parsed = schema.safeParse(data)
  if (!parsed.success) {
    console.error('Respuesta del backend con formato inesperado', path, parsed.error.issues)
    throw new ApiError('contract', 'El backend respondió con un formato inesperado. Puede haber una incompatibilidad de versiones.', res.status)
  }
  return parsed.data
}
