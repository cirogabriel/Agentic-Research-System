import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  formatByKind,
  getMetric,
  resolveGroups,
  retrievalKs,
  type Summary,
} from './metrics';

const COLORS = ['#8d7cf4', '#6bb58c', '#d9a441', '#c9554c'];

export function MetricTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="metric-tile" title={hint}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
    </div>
  );
}

/** Tarjetas de métricas agrupadas */
export function MetricGroups({ summary }: { summary: Summary | null }) {
  const groups = resolveGroups(summary);
  if (!summary || groups.length === 0)
    return (
      <p className="text-sm-muted">
        Este experimento todavía no tiene métricas.
      </p>
    );
  const ks = retrievalKs(summary);
  const chartData = ks.map((k) => ({
    k: `@${k}`,
    Recall: getMetric(summary, `retrieval.recall@${k}`),
    Precision: getMetric(summary, `retrieval.precision@${k}`),
    NDCG: getMetric(summary, `retrieval.ndcg@${k}`),
  }));
  return (
    <div className="stack">
      {groups.map((g) => (
        <section key={g.id} className="panel" aria-label={g.title}>
          <h2 style={{ marginBottom: 12 }}>{g.title}</h2>
          <div className="grid-4">
            {g.metrics.map((m) => (
              <MetricTile
                key={m.path}
                label={m.label}
                hint={m.hint}
                value={formatByKind(getMetric(summary, m.path)!, m.kind)}
              />
            ))}
          </div>
          {g.id === 'retrieval' && chartData.length > 0 && (
            <div
              className="chart-box"
              style={{ marginTop: 16 }}
              role="img"
              aria-label="Recall, Precision y NDCG por K"
            >
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="k" fontSize={11} />
                  <YAxis domain={[0, 1]} fontSize={11} />
                  <Tooltip />
                  <Legend />
                  <Bar
                    dataKey="Recall"
                    fill={COLORS[0]}
                    radius={[3, 3, 0, 0]}
                  />
                  <Bar
                    dataKey="Precision"
                    fill={COLORS[1]}
                    radius={[3, 3, 0, 0]}
                  />
                  <Bar dataKey="NDCG" fill={COLORS[2]} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
