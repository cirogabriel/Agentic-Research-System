import { request } from './api/client'
import { configurationSchema, healthSchema, type ConfigurationOut, type HealthOut } from '@/types/api'

export const systemService = {
  /** GET /health (sin autenticación) */
  health: (signal?: AbortSignal) => request<HealthOut>('/health', { schema: healthSchema, signal, timeoutMs: 10_000 }),
  /** GET /configuration: configuración efectiva sin secretos (solo lectura) */
  configuration: (signal?: AbortSignal) => request<ConfigurationOut>('/configuration', { schema: configurationSchema, signal }),
}
