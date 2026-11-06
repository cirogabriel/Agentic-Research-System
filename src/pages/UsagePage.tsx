import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState, ErrorState, LoadingState } from '@/components/common/States'
import { MetricTile } from '@/features/evaluations/MetricGroups'
import { useResearchList } from '@/features/research/queries'
import { useConfiguration } from '@/features/settings/queries'
import { formatCompact, formatNumber, formatUsd } from '@/utils/format'

export function UsagePage() {
  const research = useResearchList({ limit: 100 })
  const config = useConfiguration()
  const items = research.data?.items ?? []
  const tin = items.reduce((s, r) => s + r.tokens_input, 0)
  const tout = items.reduce((s, r) => s + r.tokens_output, 0)
  const cost = items.reduce((s, r) => s + r.cost_usd, 0)
  const chart = [...items].filter((r) => r.tokens_input + r.tokens_output > 0).slice(0, 20).reverse().map((r, i) => ({ n: `#${i + 1}`, entrada: r.tokens_input, salida: r.tokens_output }))
  const c = config.data
  const model = (label: string, value: unknown) => <MetricTile label={label} value={value === undefined ? '—' : String(value)} />

  return (
    <div className="page">
      <div className="page-header"><div><p className="eyebrow">Sistema</p><h1>Modelos y consumo</h1><p className="muted-copy">Modelos configurados en el backend y tokens consumidos por tus investigaciones.</p></div></div>
      <section className="panel">
        <h2 style={{ marginBottom: 12 }}>Modelos</h2>
        {config.isLoading ? <LoadingState rows={2} /> : config.error ? <ErrorState error={config.error} onRetry={() => void config.refetch()} /> : (
          <div className="grid-4">
            {model('Modelo generativo', c?.llm_model)}{model('Precio entrada / 1M tok', typeof c?.llm_price_input_per_mtok === 'number' ? `$${c.llm_price_input_per_mtok}` : undefined)}
            {model('Precio salida / 1M tok', typeof c?.llm_price_output_per_mtok === 'number' ? `$${c.llm_price_output_per_mtok}` : undefined)}{model('Modelo de embeddings', c?.embedding_model)}
          </div>
        )}
      </section>
      <section className="panel">
        <h2>Consumo</h2>
        <p className="panel-sub">Calculado sobre las últimas {items.length} investigaciones: el backend no expone un agregado global de consumo.</p>
        {research.isLoading ? <LoadingState rows={3} /> : research.error ? <ErrorState error={research.error} onRetry={() => void research.refetch()} />
          : items.length === 0 ? <EmptyState title="Sin consumo todavía" description="Cuando ejecutes investigaciones verás aquí sus tokens y costo estimado." /> : (
            <>
              <div className="grid-4" style={{ margin: '14px 0' }}>
                <MetricTile label="Tokens de entrada" value={formatNumber(tin)} /><MetricTile label="Tokens de salida" value={formatNumber(tout)} />
                <MetricTile label="Costo estimado" value={formatUsd(cost)} /><MetricTile label="Promedio por investigación" value={`${formatCompact((tin + tout) / items.length)} tok`} />
              </div>
              {chart.length > 0 && (
                <div className="chart-box" role="img" aria-label="Tokens por investigación">
                  <ResponsiveContainer><BarChart data={chart}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="n" fontSize={10} /><YAxis fontSize={10} width={44} tickFormatter={(v: number) => formatCompact(v)} /><Tooltip formatter={(v) => formatNumber(Number(v))} />
                    <Bar dataKey="entrada" stackId="t" fill="#8d7cf4" name="Entrada" /><Bar dataKey="salida" stackId="t" fill="#6bb58c" name="Salida" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer>
                </div>
              )}
            </>
          )}
      </section>
    </div>
  )
}
