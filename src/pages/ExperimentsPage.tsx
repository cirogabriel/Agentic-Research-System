import { useMemo, useState, Fragment } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '@/components/common/States';
import {
  formatByKind,
  getMetric,
  modeLabel,
  resolveGroups,
  unflatten,
  type MetricDef,
} from '@/features/evaluations/metrics';
import {
  isInsufficientData,
  useComparison,
  useDatasets,
  useEvaluations,
} from '@/features/evaluations/queries';
import type { ComparisonOut } from '@/types/api';
import { cn } from '@/utils/cn';

const CHARTS: {
  title: string;
  path: string;
  kind: Parameters<typeof formatByKind>[1];
}[] = [
  {
    title: 'Calidad de recuperación (MRR)',
    path: 'retrieval.mrr',
    kind: 'score',
  },
  {
    title: 'Calidad de respuestas (Answer Correctness)',
    path: 'generation.answer_correctness_f1',
    kind: 'score',
  },
  {
    title: 'Cobertura de evidencias',
    path: 'agent.evidence_coverage',
    kind: 'score',
  },
  { title: 'Latencia media', path: 'agent.latency_ms_mean', kind: 'ms' },
  { title: 'Consumo de tokens', path: 'cost.tokens_total', kind: 'int' },
  { title: 'Costo estimado (USD)', path: 'cost.cost_usd_total', kind: 'usd' },
];

function Delta({
  value,
  def,
}: {
  value: number | null | undefined;
  def: MetricDef;
}) {
  if (value === null || value === undefined || value === 0) return null;
  const good = def.lowerIsBetter ? value < 0 : value > 0;
  return (
    <span
      className="hint"
      style={{ color: good ? '#3f8a63' : '#b4423a', marginLeft: 6 }}
    >
      {value > 0 ? '+' : ''}
      {formatByKind(value, def.kind)}
    </span>
  );
}

function ComparisonView({ data }: { data: ComparisonOut }) {
  const summaries = data.experiments.map((e) => unflatten(e.metrics));
  const merged = useMemo(() => {
    const seen = new Map<string, MetricDef & { group: string }>();
    summaries.forEach((s) =>
      resolveGroups(s).forEach((g) =>
        g.metrics.forEach((m) => {
          if (!seen.has(m.path)) seen.set(m.path, { ...m, group: g.title });
        }),
      ),
    );
    const groups = new Map<string, (MetricDef & { group: string })[]>();
    seen.forEach((m) =>
      groups.set(m.group, [...(groups.get(m.group) ?? []), m]),
    );
    return [...groups.entries()];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  const label = (mode: string, name: string) =>
    mode === 'retrieval' ? name : `${mode} · ${modeLabel(mode)}`;
  return (
    <div className="stack">
      <div className="grid-3">
        {CHARTS.map((c) => {
          const rows = data.experiments
            .map((e, i) => ({
              name: e.mode,
              value: getMetric(summaries[i], c.path),
            }))
            .filter((r) => r.value !== undefined);
          if (rows.length === 0) return null;
          return (
            <section className="panel" key={c.path} style={{ marginTop: 0 }}>
              <h2 style={{ fontSize: 12 }}>{c.title}</h2>
              <div
                className="chart-box"
                style={{ height: 170 }}
                role="img"
                aria-label={c.title}
              >
                <ResponsiveContainer>
                  <BarChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" fontSize={11} />
                    <YAxis fontSize={10} width={42} />
                    <Tooltip
                      formatter={(v) => formatByKind(Number(v), c.kind)}
                    />
                    <Bar dataKey="value" fill="#8d7cf4" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          );
        })}
      </div>
      <section className="panel">
        <h2 style={{ marginBottom: 10 }}>Comparación detallada</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Métrica</th>
                {data.experiments.map((e) => (
                  <th key={e.id} className={cn('num')}>
                    {label(e.mode, e.name)}
                    {e.id === data.baseline_id && (
                      <span className="hint"> (base)</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {merged.map(([group, defs]) => (
                <Fragment key={group}>
                  <tr>
                    <td
                      colSpan={data.experiments.length + 1}
                      style={{
                        background: '#fafafc',
                        fontWeight: 700,
                        fontSize: 10,
                        letterSpacing: '.08em',
                        textTransform: 'uppercase',
                        color: '#8e8b98',
                      }}
                    >
                      {group}
                    </td>
                  </tr>
                  {defs.map((m) => (
                    <tr key={m.path}>
                      <td>{m.label}</td>
                      {data.experiments.map((e, i) => {
                        const v = getMetric(summaries[i], m.path);
                        return (
                          <td key={e.id} className="num">
                            {v === undefined ? '—' : formatByKind(v, m.kind)}
                            {e.id !== data.baseline_id && v !== undefined && (
                              <Delta
                                value={data.deltas[e.id]?.[m.path]}
                                def={m}
                              />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint" style={{ marginTop: 8 }}>
          Las diferencias se calculan respecto a la configuración base (verde =
          mejora). Fuente: GET /evaluations/experiments/compare.
        </p>
      </section>
    </div>
  );
}

export function ExperimentsPage() {
  const datasets = useDatasets();
  const [datasetId, setDatasetId] = useState('');
  const [manual, setManual] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const completed = useEvaluations({
    limit: 100,
    dataset_id: datasetId || undefined,
  });
  const options = (completed.data?.items ?? []).filter(
    (e) => e.status === 'completed',
  );
  const auto = useComparison({ dataset_id: datasetId || undefined }, !manual);
  const chosen = useComparison(
    { experiment_ids: picked },
    manual && picked.length >= 2,
  );
  const q = manual ? chosen : auto;
  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Análisis</p>
          <h1>Experimentos comparativos</h1>
          <p className="muted-copy">
            Compara RAG convencional, RAG con Supervisor y agentes, y RAG
            multiagente con verificación.
          </p>
        </div>
      </div>
      <div className="panel">
        <div className="toolbar" style={{ marginBottom: 0 }}>
          <select
            className="select"
            aria-label="Dataset"
            value={datasetId}
            onChange={(e) => {
              setDatasetId(e.target.value);
              setPicked([]);
            }}
          >
            <option value="">Todos los datasets</option>
            {(datasets.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <div className="seg" role="group" aria-label="Modo de selección">
            <button aria-pressed={!manual} onClick={() => setManual(false)}>
              Último de cada modo (A, B, C)
            </button>
            <button aria-pressed={manual} onClick={() => setManual(true)}>
              Elegir experimentos
            </button>
          </div>
        </div>
        {manual && (
          <div style={{ marginTop: 12 }}>
            {options.length === 0 ? (
              <p className="text-sm-muted">No hay experimentos completados.</p>
            ) : (
              <div
                className="doc-pick"
                role="group"
                aria-label="Experimentos completados"
              >
                {options.map((e) => (
                  <label
                    className="check"
                    key={e.id}
                    style={{ padding: '4px 0' }}
                  >
                    <input
                      type="checkbox"
                      checked={picked.includes(e.id)}
                      onChange={() => toggle(e.id)}
                    />
                    {e.name} <span className="hint">({e.mode})</span>
                  </label>
                ))}
              </div>
            )}
            {picked.length < 2 && (
              <p className="hint" style={{ marginTop: 6 }}>
                Selecciona al menos 2 experimentos.
              </p>
            )}
          </div>
        )}
      </div>
      <div style={{ marginTop: 15 }}>
        {manual && picked.length < 2 ? null : q.isLoading ? (
          <LoadingState rows={4} label="Comparando experimentos" />
        ) : q.error ? (
          isInsufficientData(q.error) ? (
            <div className="panel">
              <EmptyState
                title="Aún no hay datos suficientes"
                description="Se necesitan al menos 2 experimentos completados (por ejemplo, modos A y B) sobre el mismo dataset."
                action={
                  <Link to="/evaluations" className="link-accent">
                    Ir a Evaluaciones
                  </Link>
                }
              />
            </div>
          ) : (
            <ErrorState error={q.error} onRetry={() => void q.refetch()} />
          )
        ) : q.data ? (
          <ComparisonView data={q.data} />
        ) : null}
      </div>
    </div>
  );
}
