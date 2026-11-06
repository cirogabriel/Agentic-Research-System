import { useState, Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { MarkdownView } from '@/components/common/MarkdownView'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useReport } from '@/features/research/queries'
import type { ResearchOut } from '@/types/api'
import { formatCompact, formatDateTime, formatDuration, formatUsd, researchStatusMeta, truncate } from '@/utils/format'

/** El resumen no viene en el listado: se pide el informe solo al expandir una fila completada. */
function Summary({ id }: { id: string }) {
  const { data, isLoading, error } = useReport(id, true)
  if (isLoading) return <span className="text-sm-muted">Cargando resumen…</span>
  if (error || !data) return <span className="text-sm-muted">No se pudo cargar el resumen.</span>
  const s = data.content.executive_summary
  return <div><strong style={{ fontSize: 12 }}>{data.title}</strong>{typeof s === 'string' && <MarkdownView markdown={s} />}</div>
}

export function ResearchTable({ items }: { items: ResearchOut[] }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="table-wrap">
      <table className="table">
        <thead><tr><th aria-label="Resumen" /><th>Consulta</th><th>Creada</th><th>Estado</th><th>Duración</th><th className="num">Iter.</th><th className="num">Tokens</th><th className="num">Costo</th></tr></thead>
        <tbody>
          {items.map((r) => {
            const expanded = open === r.id
            return (
              <Fragment key={r.id}>
                <tr className="is-clickable" onClick={() => navigate(`/research/${r.id}`)}>
                  <td style={{ width: 28 }}>
                    {r.status === 'completed' && (
                      <button className="icon-button subtle" aria-expanded={expanded} aria-label={`${expanded ? 'Ocultar' : 'Ver'} resumen`} onClick={(e) => { e.stopPropagation(); setOpen(expanded ? null : r.id) }}>
                        {expanded ? <ChevronDown /> : <ChevronRight />}
                      </button>
                    )}
                  </td>
                  <td><div className="cell-title">{truncate(r.query, 110)}</div>{r.parent_id && <div className="hint">Seguimiento</div>}</td>
                  <td>{formatDateTime(r.created_at)}</td>
                  <td><StatusBadge meta={researchStatusMeta(r.status)} /></td>
                  <td>{formatDuration(r.created_at, r.finished_at) ?? '—'}</td>
                  <td className="num">{r.iterations}</td>
                  <td className="num">{formatCompact(r.tokens_input + r.tokens_output)}</td>
                  <td className="num">{formatUsd(r.cost_usd)}</td>
                </tr>
                {expanded && <tr><td /><td colSpan={7}><Summary id={r.id} /></td></tr>}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
