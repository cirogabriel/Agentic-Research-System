import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EmptyState, QueryBoundary } from '@/components/common/States'
import { Pagination } from '@/components/common/Pagination'
import { ResearchTable } from '@/features/history/ResearchRows'
import { useResearchList } from '@/features/research/queries'
import { RESEARCH_STATUSES } from '@/types/api'
import { researchStatusMeta } from '@/utils/format'

const LIMIT = 20

/** Historial cronológico. Paginación y filtro de estado son del servidor; la búsqueda de texto filtra la página cargada (el backend no ofrece búsqueda). */
export function HistoryPage() {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const { data, isLoading, error, refetch } = useResearchList({ limit: LIMIT, offset, status: status || undefined })
  const items = useMemo(() => (data?.items ?? []).filter((r) => r.query.toLowerCase().includes(q.trim().toLowerCase())), [data, q])
  return (
    <div className="page">
      <div className="page-header">
        <div><p className="eyebrow">Principal</p><h1>Historial</h1><p className="muted-copy">Todas las ejecuciones, de la más reciente a la más antigua.</p></div>
        
      </div>
      <div className="panel">
        <div className="toolbar">
          <div className="search-box"><Search /><input className="input" type="search" placeholder="Buscar en esta página…" aria-label="Buscar investigaciones" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <select className="select" aria-label="Filtrar por estado" value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0) }}>
            <option value="">Todos los estados</option>
            {RESEARCH_STATUSES.map((s) => <option key={s} value={s}>{researchStatusMeta(s).label}</option>)}
          </select>
        </div>
        <QueryBoundary isLoading={isLoading} error={error} onRetry={() => void refetch()} isEmpty={items.length === 0}
          empty={<EmptyState title={q || status ? 'Sin resultados' : 'Aún no hay investigaciones'} description={q || status ? 'Prueba con otros filtros.' : 'Cuando lances una investigación aparecerá aquí.'} />}>
          <ResearchTable items={items} />
          <Pagination offset={offset} limit={LIMIT} total={data?.total ?? 0} onChange={setOffset} />
        </QueryBoundary>
      </div>
    </div>
  )
}
