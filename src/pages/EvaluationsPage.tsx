import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FlaskConical, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EmptyState, QueryBoundary } from '@/components/common/States'
import { Pagination } from '@/components/common/Pagination'
import { StatusBadge } from '@/components/common/StatusBadge'
import { DatasetForm } from '@/features/evaluations/DatasetForm'
import { ExperimentForm } from '@/features/evaluations/ExperimentForm'
import { formatByKind, getMetric, modeLabel } from '@/features/evaluations/metrics'
import { useDatasets, useEvaluations } from '@/features/evaluations/queries'
import { evaluationStatusMeta, formatDateTime, formatDuration } from '@/utils/format'

const LIMIT = 15

export function EvaluationsPage() {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0)
  const [datasetId, setDatasetId] = useState('')
  const [dialog, setDialog] = useState<'dataset' | 'experiment' | null>(null)
  const datasets = useDatasets()
  const evals = useEvaluations({ limit: LIMIT, offset, dataset_id: datasetId || undefined })
  const names = new Map((datasets.data ?? []).map((d) => [d.id, d.name]))
  const noDatasets = !datasets.isLoading && (datasets.data?.length ?? 0) === 0

  return (
    <div className="page">
      <div className="page-header">
        <div><p className="eyebrow">Análisis</p><h1>Evaluaciones</h1><p className="muted-copy">Mide la calidad de recuperación, generación, agentes y rendimiento sobre datasets de referencia.</p></div>
        <div className="row"><Button variant="outline" onClick={() => setDialog('dataset')}><Plus /> Nuevo dataset</Button><Button className="new-research-button" disabled={noDatasets || datasets.isLoading} title={noDatasets ? 'Crea un dataset primero' : undefined} onClick={() => setDialog('experiment')}><FlaskConical /> Nuevo experimento</Button></div>
      </div>
      <div className="panel">
        <div className="toolbar">
          <select className="select" aria-label="Filtrar por dataset" value={datasetId} onChange={(e) => { setDatasetId(e.target.value); setOffset(0) }}>
            <option value="">Todos los datasets</option>
            {(datasets.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <QueryBoundary isLoading={evals.isLoading} error={evals.error} onRetry={() => void evals.refetch()} isEmpty={(evals.data?.items.length ?? 0) === 0}
          empty={<EmptyState title="Aún no hay experimentos" description={noDatasets ? 'Crea un dataset y lanza tu primer experimento.' : 'Lanza un experimento sobre uno de tus datasets.'} />}>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Experimento</th><th>Configuración</th><th>Dataset</th><th>Estado</th><th className="num">MRR</th><th className="num">Costo</th><th>Creado</th><th>Duración</th></tr></thead>
              <tbody>
                {evals.data?.items.map((e) => {
                  const mrr = getMetric(e.summary, 'retrieval.mrr'); const cost = getMetric(e.summary, 'cost.cost_usd_total')
                  return (
                    <tr key={e.id} className="is-clickable" tabIndex={0} onClick={() => navigate(`/evaluations/${e.id}`)} onKeyDown={(ev) => { if (ev.key === 'Enter') navigate(`/evaluations/${e.id}`) }}>
                      <td><div className="cell-title">{e.name}</div></td>
                      <td>{e.mode === 'retrieval' ? modeLabel(e.mode) : `${e.mode} · ${modeLabel(e.mode)}`}</td>
                      <td>{names.get(e.dataset_id) ?? '—'}</td>
                      <td><StatusBadge meta={evaluationStatusMeta(e.status)} /></td>
                      <td className="num">{mrr !== undefined ? formatByKind(mrr, 'score') : '—'}</td>
                      <td className="num">{cost !== undefined ? formatByKind(cost, 'usd') : '—'}</td>
                      <td>{formatDateTime(e.created_at)}</td>
                      <td>{formatDuration(e.created_at, e.finished_at) ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pagination offset={offset} limit={LIMIT} total={evals.data?.total ?? 0} onChange={setOffset} />
        </QueryBoundary>
      </div>
      {dialog === 'dataset' && <DatasetForm onClose={() => setDialog(null)} />}
      {dialog === 'experiment' && datasets.data && <ExperimentForm datasets={datasets.data} onClose={() => setDialog(null)} onCreated={(id) => navigate(`/evaluations/${id}`)} />}
    </div>
  )
}
