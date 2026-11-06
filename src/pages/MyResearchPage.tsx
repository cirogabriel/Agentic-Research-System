import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MessageSquare, Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EmptyState, QueryBoundary } from '@/components/common/States'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useResearchList } from '@/features/research/queries'
import { groupThreads } from '@/features/research/thread'
import { RESEARCH_STATUSES } from '@/types/api'
import { formatRelative, researchStatusMeta, truncate } from '@/utils/format'

/** Conversaciones: cada hilo agrupa una investigación y sus seguimientos (enlazados por parent_id). */
export function MyResearchPage() {
  const navigate = useNavigate()
  const { data, isLoading, error, refetch } = useResearchList({ limit: 100 })
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const threads = useMemo(() => {
    return groupThreads(data?.items ?? [])
      .map((t) => ({ ...t, last: t.turns.at(-1)! }))
      .filter((t) => (!status || t.last.status === status) && t.turns.some((x) => x.query.toLowerCase().includes(q.trim().toLowerCase())))
  }, [data, q, status])
  return (
    <div className="page">
      <div className="page-header">
        <div><p className="eyebrow">Principal</p><h1>Mis investigaciones</h1><p className="muted-copy">Tus conversaciones de investigación y sus preguntas de seguimiento.</p></div>
        <Button className="new-research-button" onClick={() => navigate('/research/new')}><Plus /> Nueva investigación</Button>
      </div>
      <div className="toolbar">
        <div className="search-box"><Search /><input className="input" type="search" placeholder="Buscar conversaciones…" aria-label="Buscar conversaciones" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="select" aria-label="Filtrar por estado" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos los estados</option>
          {RESEARCH_STATUSES.map((s) => <option key={s} value={s}>{researchStatusMeta(s).label}</option>)}
        </select>
      </div>
      <QueryBoundary isLoading={isLoading} error={error} onRetry={() => void refetch()} isEmpty={threads.length === 0}
        empty={<div className="panel"><EmptyState title={q || status ? 'Sin resultados' : 'Aún no tienes investigaciones'} description="Inicia una investigación para crear tu primera conversación." /></div>}>
        <div className="grid-3">
          {threads.map(({ root, turns, last }) => (
            <Link key={root.id} to={`/research/${last.id}`} className="panel" style={{ display: 'block', marginTop: 0 }}>
              <div className="row"><StatusBadge meta={researchStatusMeta(last.status)} /><span className="spacer text-sm-muted">{formatRelative(last.created_at)}</span></div>
              <p className="cell-title" style={{ whiteSpace: 'normal', margin: '10px 0 8px', maxWidth: 'none', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>{truncate(root.query, 160)}</p>
              <p className="text-sm-muted row" style={{ gap: 5 }}><MessageSquare size={12} /> {turns.length} {turns.length === 1 ? 'turno' : 'turnos'}</p>
            </Link>
          ))}
        </div>
        {(data?.total ?? 0) > 100 && <p className="text-sm-muted" style={{ marginTop: 12 }}>Mostrando las 100 investigaciones más recientes de {data?.total}. Usa el Historial para recorrerlas todas.</p>}
      </QueryBoundary>
    </div>
  )
}
