/**
 * Catálogo de métricas. Las claves son las que el backend escribe en `EvaluationExperiment.summary`
 * (evaluation/experiments.py::summarize y agent_metrics.summarize). Solo se muestran las que existen en el resumen.
 */
import { formatMetric, formatMs, formatNumber, formatUsd } from '@/utils/format'

export type MetricKind = 'score' | 'ms' | 'int' | 'usd' | 'count'
export interface MetricDef { path: string; label: string; kind: MetricKind; hint?: string; lowerIsBetter?: boolean }
export interface MetricGroupDef { id: string; title: string; metrics: MetricDef[] }
export type Summary = Record<string, unknown>

export const MODE_LABELS: Record<string, string> = {
  retrieval: 'Solo recuperación',
  A: 'RAG convencional',
  B: 'RAG con Supervisor y agentes',
  C: 'RAG multiagente con verificación',
}
export const modeLabel = (m: string) => MODE_LABELS[m] ?? m

const GENERATION: MetricDef[] = [
  { path: 'generation.faithfulness_lexical', label: 'Faithfulness', kind: 'score', hint: 'Fidelidad de la respuesta a los contextos (léxica)' },
  { path: 'generation.answer_relevancy_lexical', label: 'Answer Relevancy', kind: 'score' },
  { path: 'generation.answer_correctness_f1', label: 'Answer Correctness', kind: 'score', hint: 'F1 frente a la respuesta de referencia' },
  { path: 'generation.context_precision_doc', label: 'Context Precision', kind: 'score' },
  { path: 'generation.context_recall_lexical', label: 'Context Recall', kind: 'score' },
]
const AGENTS: MetricDef[] = [
  { path: 'agent.task_completion_rate', label: 'Task Completion Rate', kind: 'score' },
  { path: 'agent.tool_selection_accuracy', label: 'Tool Selection Accuracy', kind: 'score' },
  { path: 'agent.delegation_accuracy', label: 'Delegation Accuracy', kind: 'score' },
  { path: 'agent.citation_accuracy', label: 'Citation Accuracy', kind: 'score' },
  { path: 'agent.evidence_coverage', label: 'Evidence Coverage', kind: 'score' },
  { path: 'agent.iterations_per_task', label: 'Iterations per Task', kind: 'count', lowerIsBetter: true },
  { path: 'agent.agent_failure_rate', label: 'Agent Failure Rate', kind: 'score', lowerIsBetter: true },
]
const PERFORMANCE: MetricDef[] = [
  { path: 'retrieval.retrieval_latency_ms', label: 'Latencia de recuperación', kind: 'ms', lowerIsBetter: true },
  { path: 'agent.latency_ms_mean', label: 'Latencia media', kind: 'ms', lowerIsBetter: true },
  { path: 'agent.latency_ms_p50', label: 'Latencia p50', kind: 'ms', lowerIsBetter: true },
  { path: 'agent.latency_ms_p95', label: 'Latencia p95', kind: 'ms', lowerIsBetter: true },
  { path: 'agent.tokens_input_total', label: 'Tokens de entrada', kind: 'int', lowerIsBetter: true },
  { path: 'agent.tokens_output_total', label: 'Tokens de salida', kind: 'int', lowerIsBetter: true },
  { path: 'cost.tokens_total', label: 'Tokens totales', kind: 'int', lowerIsBetter: true },
  { path: 'cost.cost_usd_total', label: 'Costo estimado total', kind: 'usd', lowerIsBetter: true },
  { path: 'cost.cost_usd_per_item', label: 'Costo estimado por ítem', kind: 'usd', lowerIsBetter: true },
]

export function getMetric(summary: Summary | null | undefined, path: string): number | undefined {
  const [section, key] = path.split('.') as [string, string]
  const group = summary?.[section]
  if (!group || typeof group !== 'object') return undefined
  const v = (group as Record<string, unknown>)[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

const KS = (summary: Summary | null | undefined): number[] => {
  const r = summary?.retrieval
  if (!r || typeof r !== 'object') return []
  return [...new Set(Object.keys(r).map((k) => /^recall@(\d+)$/.exec(k)?.[1]).filter((x): x is string => !!x).map(Number))].sort((a, b) => a - b)
}
export const retrievalKs = KS

function retrievalDefs(summary: Summary | null | undefined): MetricDef[] {
  const defs: MetricDef[] = []
  for (const k of KS(summary)) {
    defs.push({ path: `retrieval.recall@${k}`, label: `Recall@${k}`, kind: 'score' }, { path: `retrieval.precision@${k}`, label: `Precision@${k}`, kind: 'score' })
  }
  defs.push({ path: 'retrieval.mrr', label: 'MRR', kind: 'score', hint: 'Mean Reciprocal Rank' })
  for (const k of KS(summary)) defs.push({ path: `retrieval.ndcg@${k}`, label: `NDCG@${k}`, kind: 'score' })
  return defs
}

function ragasDefs(summary: Summary | null | undefined): MetricDef[] {
  const r = summary?.ragas
  if (!r || typeof r !== 'object') return []
  return Object.entries(r as Record<string, unknown>).filter(([, v]) => typeof v === 'number').map(([k]) => ({ path: `ragas.${k}`, label: `RAGAS · ${k.replace(/^ragas_/, '').replace(/_/g, ' ')}`, kind: 'score' as const }))
}

/** Grupos con solo las métricas presentes en este resumen. */
export function resolveGroups(summary: Summary | null | undefined): MetricGroupDef[] {
  const all: MetricGroupDef[] = [
    { id: 'retrieval', title: 'Recuperación', metrics: retrievalDefs(summary) },
    { id: 'generation', title: 'Generación', metrics: [...GENERATION, ...ragasDefs(summary)] },
    { id: 'agents', title: 'Agentes', metrics: AGENTS },
    { id: 'performance', title: 'Rendimiento', metrics: PERFORMANCE },
  ]
  return all.map((g) => ({ ...g, metrics: g.metrics.filter((m) => getMetric(summary, m.path) !== undefined) })).filter((g) => g.metrics.length > 0)
}

export function formatByKind(value: number, kind: MetricKind): string {
  switch (kind) {
    case 'ms': return formatMs(value)
    case 'int': return formatNumber(Math.round(value))
    case 'usd': return formatUsd(value)
    case 'count': return value.toFixed(2)
    default: return formatMetric(value)
  }
}

/** {'retrieval.mrr': 1} → {retrieval: {mrr: 1}} (inversa de `flatten` del backend, usada por /experiments/compare). */
export function unflatten(flat: Record<string, number>): Summary {
  const out: Record<string, Record<string, number>> = {}
  for (const [path, v] of Object.entries(flat)) {
    const dot = path.indexOf('.')
    if (dot === -1) continue
    const section = path.slice(0, dot)
    ;(out[section] ??= {})[path.slice(dot + 1)] = v
  }
  return out
}
