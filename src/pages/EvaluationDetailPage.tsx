import { useState, Fragment } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { ErrorState, LoadingState } from '@/components/common/States';
import { StatusBadge } from '@/components/common/StatusBadge';
import { MetricGroups } from '@/features/evaluations/MetricGroups';
import { modeLabel } from '@/features/evaluations/metrics';
import { useEvaluation } from '@/features/evaluations/queries';
import {
  evaluationStatusMeta,
  formatDateTime,
  formatDuration,
  formatMs,
  formatNumber,
  truncate,
} from '@/utils/format';

export function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: e, isLoading, error, refetch } = useEvaluation(id);
  const [open, setOpen] = useState<string | null>(null);
  if (isLoading)
    return (
      <div className="page">
        <LoadingState rows={5} label="Cargando evaluación" />
      </div>
    );
  if (error || !e)
    return (
      <div className="page">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    );
  const running = e.status === 'pending' || e.status === 'running';
  return (
    <div className="page">
      <Link
        to="/evaluations"
        className="link-accent row"
        style={{ marginBottom: 12, gap: 4 }}
      >
        <ArrowLeft size={13} /> Evaluaciones
      </Link>
      <div className="page-header">
        <div>
          <p className="eyebrow">
            {e.mode === 'retrieval'
              ? modeLabel(e.mode)
              : `${e.mode} · ${modeLabel(e.mode)}`}
          </p>
          <h1>{e.name}</h1>
          <p className="muted-copy row-wrap" style={{ gap: 8 }}>
            <StatusBadge meta={evaluationStatusMeta(e.status)} />
            <span>Creado {formatDateTime(e.created_at)}</span>
            {formatDuration(e.created_at, e.finished_at) && (
              <span>· {formatDuration(e.created_at, e.finished_at)}</span>
            )}
          </p>
        </div>
      </div>
      {running && (
        <div className="banner info" role="status" style={{ marginBottom: 15 }}>
          <span className="spinner" /> El experimento se está ejecutando en el
          backend. Esta página se actualiza sola.
        </div>
      )}
      {e.status === 'failed' && (
        <div className="banner error" role="alert" style={{ marginBottom: 15 }}>
          El experimento falló durante su ejecución en el backend. Revisa los
          registros del servicio para ver el detalle técnico.
        </div>
      )}
      <details className="panel" style={{ marginBottom: 15 }}>
        <summary style={{ cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
          Configuración utilizada
        </summary>
        <dl className="kv" style={{ marginTop: 10 }}>
          {Object.entries(e.config).map(([k, v]) => (
            <Fragment key={k}>
              <dt>{k}</dt>
              <dd>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
            </Fragment>
          ))}
        </dl>
      </details>
      <MetricGroups summary={e.summary} />
      {e.results.length > 0 && (
        <section className="panel" style={{ marginTop: 15 }}>
          <h2 style={{ marginBottom: 10 }}>
            Resultados por ítem ({e.results.length})
          </h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Pregunta</th>
                  <th>Estado</th>
                  <th className="num">Latencia</th>
                  <th className="num">Tokens</th>
                  <th className="num">Iter.</th>
                </tr>
              </thead>
              <tbody>
                {e.results.map((r) => (
                  <Fragment key={r.item_id}>
                    <tr
                      className="is-clickable"
                      tabIndex={0}
                      aria-expanded={open === r.item_id}
                      onClick={() =>
                        setOpen(open === r.item_id ? null : r.item_id)
                      }
                      onKeyDown={(ev) => {
                        if (ev.key === 'Enter')
                          setOpen(open === r.item_id ? null : r.item_id);
                      }}
                    >
                      <td>
                        <div className="cell-title">
                          {truncate(r.question, 110)}
                        </div>
                      </td>
                      <td>
                        {r.status === 'error' ? (
                          <span className="badge error">Error</span>
                        ) : (
                          <span className="badge complete">OK</span>
                        )}
                      </td>
                      <td className="num">{formatMs(r.latency_ms)}</td>
                      <td className="num">
                        {formatNumber(r.tokens_input + r.tokens_output)}
                      </td>
                      <td className="num">{r.iterations}</td>
                    </tr>
                    {open === r.item_id && (
                      <tr>
                        <td colSpan={5}>
                          {r.answer && (
                            <p
                              style={{
                                whiteSpace: 'pre-wrap',
                                margin: '0 0 8px',
                              }}
                            >
                              {r.answer}
                            </p>
                          )}
                          {r.retrieved.length > 0 && (
                            <p className="hint">
                              Recuperados: {r.retrieved.join(', ')}
                            </p>
                          )}
                          <p className="hint">
                            Métricas:{' '}
                            {Object.entries(r.metrics)
                              .filter(([, v]) => typeof v === 'number')
                              .map(
                                ([k, v]) => `${k}=${(v as number).toFixed(3)}`,
                              )
                              .join(' · ') || '—'}
                          </p>
                          {r.error && (
                            <p className="field-error">
                              Este ítem falló durante la evaluación.
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
