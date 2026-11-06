import { QUERY_TRANSFORMS, RETRIEVAL_STRATEGIES, type QueryTransform, type RetrievalStrategy } from '@/types/api'
import type { ResearchDefaults } from '@/stores/preferencesStore'
import { OPTION_LIMITS, validateDefaults } from './options'

const STRATEGY_LABEL: Record<RetrievalStrategy, string> = { auto: 'Automática', vector: 'Vectorial', keyword: 'Palabras clave', hybrid: 'Híbrida' }
const TRANSFORM_LABEL: Record<QueryTransform, string> = { auto: 'Automática', none: 'Ninguna', rewrite: 'Reescritura', multi_query: 'Multi-consulta', rag_fusion: 'RAG Fusion', hyde: 'HyDE' }

interface Props {
  value: ResearchDefaults
  onChange: (v: ResearchDefaults) => void
  /** Valores efectivos del backend (GET /configuration) para mostrarlos como referencia. */
  backend?: { max_iterations?: unknown; token_budget?: unknown; retrieval_top_k?: unknown }
  idPrefix?: string
}

const toNum = (s: string): number | null => (s.trim() === '' ? null : Number(s))

export function OptionsForm({ value, onChange, backend, idPrefix = 'opt' }: Props) {
  const errors = validateDefaults(value)
  const set = <K extends keyof ResearchDefaults>(k: K, v: ResearchDefaults[K]) => onChange({ ...value, [k]: v })
  const ph = (v: unknown) => (typeof v === 'number' ? `Backend: ${v}` : 'Valor del backend')
  const num = (key: 'max_iterations' | 'token_budget' | 'top_k', label: string, backendValue: unknown) => (
    <div className="field">
      <label htmlFor={`${idPrefix}-${key}`}>{label}</label>
      <input
        id={`${idPrefix}-${key}`} className="input" type="number" inputMode="numeric"
        min={OPTION_LIMITS[key].min} max={OPTION_LIMITS[key].max}
        value={value[key] ?? ''} placeholder={ph(backendValue)}
        aria-invalid={!!errors[key]} aria-describedby={errors[key] ? `${idPrefix}-${key}-err` : undefined}
        onChange={(e) => set(key, toNum(e.target.value))}
      />
      {errors[key] ? <span id={`${idPrefix}-${key}-err`} className="field-error">{errors[key]}</span> : <span className="hint">{OPTION_LIMITS[key].min}–{OPTION_LIMITS[key].max}. Vacío = valor del backend.</span>}
    </div>
  )
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="form-grid">
        {num('max_iterations', 'Máx. iteraciones', backend?.max_iterations)}
        {num('token_budget', 'Presupuesto de tokens', backend?.token_budget)}
        {num('top_k', 'Resultados por búsqueda (top-k)', backend?.retrieval_top_k)}
        <div className="field">
          <label htmlFor={`${idPrefix}-strategy`}>Estrategia de recuperación</label>
          <select id={`${idPrefix}-strategy`} className="select" value={value.retrieval_strategy ?? ''} onChange={(e) => set('retrieval_strategy', (e.target.value || null) as RetrievalStrategy | null)}>
            <option value="">Valor del backend</option>
            {RETRIEVAL_STRATEGIES.map((s) => <option key={s} value={s}>{STRATEGY_LABEL[s]}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${idPrefix}-transform`}>Transformación de consulta</label>
          <select id={`${idPrefix}-transform`} className="select" value={value.query_transform ?? ''} onChange={(e) => set('query_transform', (e.target.value || null) as QueryTransform | null)}>
            <option value="">Valor del backend</option>
            {QUERY_TRANSFORMS.map((s) => <option key={s} value={s}>{TRANSFORM_LABEL[s]}</option>)}
          </select>
        </div>
      </div>
      <div className="row-wrap" style={{ gap: 22 }}>
        <label className="check"><input type="checkbox" checked={value.parallel} onChange={(e) => set('parallel', e.target.checked)} /> Subtareas en paralelo</label>
        <label className="check"><input type="checkbox" checked={value.reinvestigate} onChange={(e) => set('reinvestigate', e.target.checked)} /> Permitir reinvestigación</label>
      </div>
    </div>
  )
}
