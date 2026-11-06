import { useEffect, useRef } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/components/common/States'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useResearchStream } from '@/hooks/useResearchStream'
import { ResearchComposer } from '@/features/research/ResearchComposer'
import { AgentActivityPanel, ProgressInline, ProgressPanel, RunMetricsCard } from '@/features/research/ProgressPanels'
import { TurnView } from '@/features/research/TurnView'
import { useCreateResearch, useReport, useResearchStatus, useResearchThread } from '@/features/research/queries'
import { canFollowUp } from '@/features/research/thread'
import { isApiError } from '@/services/api'
import { notify } from '@/stores/toastStore'
import { formatDate, formatDuration, isActiveResearch, researchStatusMeta, truncate } from '@/utils/format'

export function ResearchPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { turns, isLoading, error, refetch } = useResearchThread(id)
  const last = turns.at(-1)
  const active = !!last && isActiveResearch(last.status)
  const stream = useResearchStream(last?.id, last?.status)
  const status = useResearchStatus(last?.id, active)
  const report = useReport(last?.id, last?.status === 'completed')
  const create = useCreateResearch()
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [stream.events.length, last?.status, turns.length])

  if (isLoading) return <div className="page"><LoadingState label="Cargando investigación" rows={5} /></div>
  if (error || !last) {
    const notFound = isApiError(error) && error.kind === 'not_found'
    return <div className="page"><ErrorState error={error} onRetry={refetch} title={notFound ? 'La investigación no existe' : 'No se pudo cargar la investigación'} /><p style={{ textAlign: 'center' }}><Link to="/research" className="link-accent">Ir a Mis investigaciones</Link></p></div>
  }

  const first = turns[0]!
  const title = report.data?.title ?? truncate(first.query, 80)
  const disabledReason =
    active ? 'La investigación está en curso. Podrás hacer una pregunta de seguimiento cuando termine.'
    : last.status === 'needs_clarification' ? 'Responde primero a las aclaraciones solicitadas.'
    : !canFollowUp(last) ? 'Reanuda o reintenta la investigación para poder continuar la conversación.'
    : undefined
  const duration = formatDuration(last.created_at, last.finished_at)

  return (
    <div className="page-grid">
      <main className="conversation-column">
        <div className="conversation-heading">
          <div className="min-w-0">
            <p className="eyebrow">{turns.length > 1 ? `Conversación · ${turns.length} turnos` : 'Investigación'}</p>
            <h1 style={{ overflowWrap: 'anywhere' }}>{title}</h1>
            <p className="muted-copy row-wrap" style={{ gap: 8 }}>
              <span>Iniciada el {formatDate(first.created_at)}</span>
              <StatusBadge meta={researchStatusMeta(last.status)} />
              {duration && <span>· {duration}</span>}
            </p>
          </div>
          {stream.connection === 'failed' && !stream.progress.terminal && <Button size="xs" variant="outline" onClick={stream.reconnect}><RefreshCw /> Reconectar</Button>}
        </div>

        <ProgressInline progress={stream.progress} />

        <div className="chat-stream" aria-live="off">
          <div className="date-marker"><span /> {formatDate(first.created_at)} <span /></div>
          {turns.map((t) => <TurnView key={t.id} turn={t} stream={t.id === last.id ? stream : undefined} />)}
          <div ref={endRef} />
        </div>

        <ResearchComposer
          key={last.id} pending={create.isPending} disabledReason={disabledReason} submitLabel="Enviar"
          placeholder="Haz una pregunta de seguimiento…"
          onSubmit={(query, options) =>
            create.mutate({ query, options, parent_research_id: last.id }, { onSuccess: (r) => { notify.success('Seguimiento iniciado'); navigate(`/research/${r.id}`) } })
          }
        />
      </main>

      <aside className="right-rail">
        <ProgressPanel stream={stream} title={title} />
        <AgentActivityPanel progress={stream.progress} />
        <RunMetricsCard status={status.data} />
      </aside>
    </div>
  )
}
