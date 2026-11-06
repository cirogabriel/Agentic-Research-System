const LOCALE = 'es'

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeStyle: 'short' }).format(d)
}
export function formatDate(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : new Intl.DateTimeFormat(LOCALE, { dateStyle: 'long' }).format(d)
}
export function formatTime(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : new Intl.DateTimeFormat(LOCALE, { hour: '2-digit', minute: '2-digit' }).format(d)
}

export function formatRelative(iso?: string | null, now: number = Date.now()): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return '—'
  const diffSec = Math.round((t - now) / 1000)
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: 'auto' })
  const abs = Math.abs(diffSec)
  if (abs < 45) return rtf.format(0, 'second')
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), 'hour')
  if (abs < 86400 * 30) return rtf.format(Math.round(diffSec / 86400), 'day')
  return formatDate(iso)
}

/** Duración entre dos instantes, p. ej. "2 min 14 s". Devuelve null si falta alguno. */
export function formatDuration(startIso?: string | null, endIso?: string | null): string | null {
  if (!startIso || !endIso) return null
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime()
  if (!Number.isFinite(ms) || ms < 0) return null
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} min ${s % 60} s`
  return `${Math.floor(m / 60)} h ${m % 60} min`
}

export function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat(LOCALE).format(n)
}
export function formatCompact(n: number): string {
  return new Intl.NumberFormat(LOCALE, { notation: 'compact', maximumFractionDigits: 1 }).format(n)
}
export function formatUsd(n: number): string {
  const digits = n !== 0 && Math.abs(n) < 0.01 ? 5 : 3
  return `$${n.toFixed(digits)}`
}
export function formatPercent(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`
}
export function formatMetric(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(3).replace(/\.?0+$/, '')
}

export function truncate(text: string, max: number): string {
  const t = text.replace(/\s+/g, ' ').trim()
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

export type Tone = 'live' | 'complete' | 'error' | 'warn' | 'idle'
export interface StatusMeta { label: string; tone: Tone }

const RESEARCH: Record<string, StatusMeta> = {
  pending: { label: 'En cola', tone: 'idle' },
  running: { label: 'En progreso', tone: 'live' },
  completed: { label: 'Completada', tone: 'complete' },
  failed: { label: 'Fallida', tone: 'error' },
  needs_clarification: { label: 'Requiere aclaración', tone: 'warn' },
  interrupted: { label: 'Interrumpida', tone: 'warn' },
}
const DOCUMENT: Record<string, StatusMeta> = {
  processing: { label: 'Procesando', tone: 'live' },
  indexed: { label: 'Indexado', tone: 'complete' },
  failed: { label: 'Fallido', tone: 'error' },
}
const EVALUATION: Record<string, StatusMeta> = {
  pending: { label: 'En cola', tone: 'idle' },
  running: { label: 'En ejecución', tone: 'live' },
  completed: { label: 'Completado', tone: 'complete' },
  failed: { label: 'Fallido', tone: 'error' },
}
const fallback = (s: string): StatusMeta => ({ label: s, tone: 'idle' })
export const researchStatusMeta = (s: string): StatusMeta => RESEARCH[s] ?? fallback(s)
export const documentStatusMeta = (s: string): StatusMeta => DOCUMENT[s] ?? fallback(s)
export const evaluationStatusMeta = (s: string): StatusMeta => EVALUATION[s] ?? fallback(s)
export const isActiveResearch = (s: string) => s === 'pending' || s === 'running'
