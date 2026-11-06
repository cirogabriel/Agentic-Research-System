import { Bot, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ResearchStream } from '@/hooks/useResearchStream'
import type { ResearchStatusOut } from '@/types/api'
import type { ResearchEvent } from '@/types/events'
import { formatNumber, formatTime, formatUsd, truncate } from '@/utils/format'
import { cn } from '@/utils/cn'
import { currentStageLabel, type ProgressView } from './progress'

const ICON = { completed: '✓', running: '•', failed: '✕', pending: '○' } as const
const CONNECTION_LABEL = { connecting: 'CONECTANDO', live: 'EN VIVO', reconnecting: 'RECONECTANDO', ended: 'FINALIZADA', failed: 'SIN CONEXIÓN' } as const

/** Panel oscuro del diseño: etapas reales derivadas de los eventos SSE. */
export function ProgressPanel({ stream, title }: { stream: ResearchStream; title: string }) {
  const { progress, connection, reconnect } = stream
  const running = progress.agents.find((a) => a.state === 'running')
  const label = progress.terminal ? 'FINALIZADA' : CONNECTION_LABEL[connection]
  return (
    <section className="dark-panel progress-panel" aria-label="Progreso de la investigación">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="eyebrow light">{progress.terminal ? 'Investigación' : 'Investigación en curso'}</p>
          <h2 className="mt-2 text-lg font-semibold text-white" style={{ overflowWrap: 'anywhere' }}>{truncate(title, 70)}</h2>
        </div>
        <span className="live-pill" style={connection === 'failed' ? { color: '#ff9b92' } : undefined}><span style={connection === 'failed' ? { background: '#c9554c' } : connection === 'reconnecting' ? { background: '#d9a441' } : undefined} /> {label}</span>
      </div>
      <div className="progress-line" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress.percent}><div style={{ width: `${progress.percent}%` }} /></div>
      <div className="mt-2 flex items-center justify-between text-[11px] text-white/50">
        <span>{currentStageLabel(progress) ?? (progress.terminal === 'completed' ? 'Completada' : 'En espera')}{progress.iteration > 1 ? ` · iteración ${progress.iteration}` : ''}</span>
        <span>{progress.percent}%</span>
      </div>
      <div className="stage-list">
        {progress.stages.map((s) => (
          <div className={cn('stage-row', s.state === 'completed' && 'done', s.state === 'running' && 'current', s.state === 'failed' && 'failed')} key={s.key}>
            <span className="stage-icon">{ICON[s.state]}</span>
            <span>{s.label}</span>
            {s.state === 'running' && <span className="ml-auto text-[10px] text-[#b7a5ff]">activa</span>}
          </div>
        ))}
      </div>
      {connection === 'failed' && !progress.terminal && (
        <Button size="xs" variant="outline" className="mt-4 w-full" style={{ background: 'transparent', color: '#fff', borderColor: '#4b455e' }} onClick={reconnect}><RefreshCw /> Reintentar conexión</Button>
      )}
      {(running || progress.terminal === 'failed') && (
        <div className="agent-note">
          <div className="agent-orb"><Bot /></div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-white">{running?.label ?? 'Error'}</p>
            <p className="mt-0.5 text-[10px] leading-4 text-white/45">{running?.detail ?? progress.errorMessage}</p>
          </div>
        </div>
      )}
    </section>
  )
}

/** Versión compacta para móvil, donde el panel oscuro se oculta (diseño original: ≤820px). */
export function ProgressInline({ progress }: { progress: ProgressView }) {
  if (progress.terminal && progress.terminal !== 'failed') return null
  return (
    <section className="dark-panel progress-inline" aria-label="Progreso resumido">
      <div className="flex items-center justify-between text-[11px] text-white/70"><span>{currentStageLabel(progress) ?? 'En espera'}</span><span>{progress.percent}%</span></div>
      <div className="progress-line" style={{ marginTop: 8 }}><div style={{ width: `${progress.percent}%` }} /></div>
    </section>
  )
}

/** Actividad de los 5 agentes, según los eventos recibidos. */
export function AgentActivityPanel({ progress }: { progress: ProgressView }) {
  return (
    <section className="activity-card" aria-label="Actividad de agentes">
      <div className="mb-3">
        <p className="eyebrow">Actividad de agentes</p>
        <p className="mt-1 text-xs text-muted-foreground">Según los eventos emitidos por el backend</p>
      </div>
      {progress.agents.map((a) => (
        <div className="agent-row" key={a.key}>
          <span className={cn('agent-state', a.state)} aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold">{a.label} <span className="sr-only">estado {a.state}</span></p>
            <p className="text-[11px] text-muted-foreground" style={{ overflowWrap: 'anywhere' }}>{a.detail ? truncate(a.detail, 120) : { pending: 'Pendiente', running: 'En ejecución', completed: 'Completado', failed: 'Falló' }[a.state]}</p>
          </div>
          {a.at && <span className="whitespace-nowrap text-[10px] text-muted-foreground/70">{formatTime(a.at)}</span>}
        </div>
      ))}
      {progress.tasksStarted > 0 && <p className="text-sm-muted" style={{ marginTop: 10 }}>Subtareas: {progress.tasksCompleted}/{progress.tasksStarted} completadas</p>}
      {progress.notes.map((n, i) => <p key={i} className="field-error" style={{ marginTop: 6 }}>{n}</p>)}
    </section>
  )
}

export function RunMetricsCard({ status }: { status?: ResearchStatusOut }) {
  if (!status) return null
  return (
    <section className="metric-card" aria-label="Consumo de la investigación">
      <p className="eyebrow">Consumo</p>
      <div className="metric-row"><div><p className="metric-label">Tokens de entrada / salida</p><p className="metric-value" style={{ fontSize: 17 }}>{formatNumber(status.tokens_input)} / {formatNumber(status.tokens_output)}</p></div></div>
      <div className="metric-row"><div><p className="metric-label">Costo estimado</p><p className="metric-value">{formatUsd(status.cost_usd)}</p></div><span className="metric-change neutral">{formatNumber(status.embedding_tokens)} tok. embedding</span></div>
      <div className="metric-row"><div><p className="metric-label">Iteraciones</p><p className="metric-value">{status.iteration}</p></div></div>
    </section>
  )
}

export function EventTimeline({ events, limit = 6 }: { events: ResearchEvent[]; limit?: number }) {
  const last = events.slice(-limit)
  if (!last.length) return null
  return (
    <ol className="timeline" aria-label="Eventos recientes" style={{ listStyle: 'none', padding: 0 }}>
      {last.map((e) => (
        <li className="timeline-item" key={e.id}><span className="dot" /><span style={{ overflowWrap: 'anywhere' }}>{e.message}</span><time dateTime={e.at}>{formatTime(e.at)}</time></li>
      ))}
    </ol>
  )
}

/** Mensaje de la IA mientras la investigación se ejecuta. */
export function RunningMessage({ stream }: { stream: ResearchStream }) {
  const { progress, connection, events } = stream
  return (
    <div className="message ai-message">
      <div className="message-avatar ai-icon"><Loader2 className="animate-spin" /></div>
      <div className="message-body ai-body" style={{ flex: 1, minWidth: 0 }} role="status" aria-live="polite">
        <p className="message-meta">Sistema de investigación · trabajando…</p>
        <p style={{ fontWeight: 600, color: '#34313f' }}>{currentStageLabel(progress) ?? (connection === 'connecting' ? 'Conectando con el backend…' : 'En cola, esperando a un worker…')}</p>
        {connection === 'reconnecting' && <p className="text-sm-muted">Conexión perdida; reintentando sin perder el progreso…</p>}
        {progress.plannedTasks.length > 0 && <p className="text-sm-muted" style={{ marginTop: 6 }}>Plan: {progress.plannedTasks.join(' · ')}</p>}
        <EventTimeline events={events} />
      </div>
    </div>
  )
}
