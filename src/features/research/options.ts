import type { ResearchOptions } from '@/types/api'
import type { ResearchDefaults } from '@/stores/preferencesStore'

/** Rangos validados por el backend (ResearchOptions en schemas/api.py). */
export const OPTION_LIMITS = {
  max_iterations: { min: 1, max: 10 },
  token_budget: { min: 2000, max: 2_000_000 },
  top_k: { min: 1, max: 20 },
} as const

export type OptionErrors = Partial<Record<'max_iterations' | 'token_budget' | 'top_k', string>>

export function validateDefaults(d: ResearchDefaults): OptionErrors {
  const errors: OptionErrors = {}
  for (const key of ['max_iterations', 'token_budget', 'top_k'] as const) {
    const v = d[key]
    const { min, max } = OPTION_LIMITS[key]
    if (v !== null && (!Number.isInteger(v) || v < min || v > max)) errors[key] = `Debe ser un entero entre ${min} y ${max}`
  }
  return errors
}

/** Solo se envían los parámetros que el usuario fijó; el resto lo decide el backend con sus variables de entorno. */
export function buildOptions(d: ResearchDefaults, documentIds: string[]): ResearchOptions {
  const o: ResearchOptions = { parallel: d.parallel, reinvestigate: d.reinvestigate }
  if (d.max_iterations !== null) o.max_iterations = d.max_iterations
  if (d.token_budget !== null) o.token_budget = d.token_budget
  if (d.top_k !== null) o.top_k = d.top_k
  if (d.retrieval_strategy !== null) o.retrieval_strategy = d.retrieval_strategy
  if (d.query_transform !== null) o.query_transform = d.query_transform
  if (documentIds.length) o.document_ids = documentIds
  return o
}

export const QUERY_MIN = 5
export const QUERY_MAX = 4000
export function validateQuery(q: string): string | null {
  const t = q.trim()
  if (t.length < QUERY_MIN) return `La pregunta debe tener al menos ${QUERY_MIN} caracteres`
  if (t.length > QUERY_MAX) return `La pregunta no puede superar ${QUERY_MAX} caracteres`
  return null
}
