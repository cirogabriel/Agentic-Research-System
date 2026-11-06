import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Modal } from '@/components/common/Modal'
import { useConfiguration } from '@/features/settings/queries'
import { EVALUATION_MODES, RETRIEVAL_STRATEGIES, type DatasetOut, type EvaluationCreate, type EvaluationMode, type RetrievalStrategy } from '@/types/api'
import { OPTION_LIMITS } from '@/features/research/options'
import { modeLabel } from './metrics'
import { useCreateEvaluation } from './queries'

export function ExperimentForm({ datasets, onClose, onCreated }: { datasets: DatasetOut[]; onClose: () => void; onCreated: (id: string) => void }) {
  const create = useCreateEvaluation()
  const config = useConfiguration()
  const [f, setF] = useState({ name: '', dataset_id: datasets[0]?.id ?? '', mode: 'retrieval' as EvaluationMode, top_k: 5, retrieval_strategy: 'hybrid' as RetrievalStrategy, use_ragas: false, max_iterations: '' })
  const [confirmed, setConfirmed] = useState(false)
  const consumesLlm = f.mode !== 'retrieval' || f.use_ragas
  const iterOk = f.max_iterations === '' || (Number(f.max_iterations) >= OPTION_LIMITS.max_iterations.min && Number(f.max_iterations) <= OPTION_LIMITS.max_iterations.max)
  const valid = f.name.trim().length > 0 && !!f.dataset_id && f.top_k >= 1 && f.top_k <= 20 && iterOk && (!consumesLlm || confirmed)
  const dataset = datasets.find((d) => d.id === f.dataset_id)

  const submit = () => {
    const body: EvaluationCreate = { name: f.name.trim(), dataset_id: f.dataset_id, mode: f.mode, top_k: f.top_k, retrieval_strategy: f.retrieval_strategy, use_ragas: f.use_ragas }
    if (f.max_iterations !== '' && f.mode !== 'retrieval') body.max_iterations = Number(f.max_iterations)
    create.mutate(body, { onSuccess: (e) => { onCreated(e.id); onClose() } })
  }
  return (
    <Modal title="Nuevo experimento" onClose={onClose} description="Se ejecuta en segundo plano en el backend.">
      <div className="stack" style={{ gap: 12 }}>
        <div className="field"><label htmlFor="ex-name">Nombre</label><input id="ex-name" className="input" value={f.name} maxLength={128} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div className="field"><label htmlFor="ex-ds">Dataset{dataset ? ` (${dataset.items.length} ítems)` : ''}</label>
          <select id="ex-ds" className="select" value={f.dataset_id} onChange={(e) => setF({ ...f, dataset_id: e.target.value })}>{datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
        <div className="field"><label htmlFor="ex-mode">Configuración del sistema</label>
          <select id="ex-mode" className="select" value={f.mode} onChange={(e) => setF({ ...f, mode: e.target.value as EvaluationMode })}>{EVALUATION_MODES.map((m) => <option key={m} value={m}>{m === 'retrieval' ? modeLabel(m) : `${m} · ${modeLabel(m)}`}</option>)}</select></div>
        <div className="form-grid">
          <div className="field"><label htmlFor="ex-k">Top-k</label><input id="ex-k" className="input" type="number" min={1} max={20} value={f.top_k} onChange={(e) => setF({ ...f, top_k: Number(e.target.value) })} /></div>
          <div className="field"><label htmlFor="ex-strat">Estrategia</label><select id="ex-strat" className="select" value={f.retrieval_strategy} onChange={(e) => setF({ ...f, retrieval_strategy: e.target.value as RetrievalStrategy })}>{RETRIEVAL_STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
          {f.mode !== 'retrieval' && <div className="field"><label htmlFor="ex-it">Máx. iteraciones</label><input id="ex-it" className="input" type="number" placeholder={`Backend: ${String(config.data?.max_iterations ?? '—')}`} value={f.max_iterations} aria-invalid={!iterOk} onChange={(e) => setF({ ...f, max_iterations: e.target.value })} /></div>}
        </div>
        <label className="check"><input type="checkbox" checked={f.use_ragas} onChange={(e) => setF({ ...f, use_ragas: e.target.checked })} /> Calcular métricas RAGAS (requiere LLM)</label>
        {consumesLlm && (
          <div className="banner" role="note">
            <label className="check" style={{ color: 'inherit' }}><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> Entiendo que este experimento invocará el LLM del backend y consumirá tokens (costo real).</label>
          </div>
        )}
      </div>
      <div className="modal-actions"><Button variant="outline" onClick={onClose}>Cancelar</Button><Button onClick={submit} disabled={!valid || create.isPending}>{create.isPending ? 'Lanzando…' : 'Lanzar experimento'}</Button></div>
    </Modal>
  )
}
