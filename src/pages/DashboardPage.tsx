import { Link, useNavigate } from 'react-router-dom'
import { BarChart3, FileText, Loader2, MessageSquarePlus, Plus, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState } from '@/components/common/States'
import { useDocumentCount } from '@/features/documents/queries'
import { useResearchCount, useResearchList } from '@/features/research/queries'
import { formatCompact, formatDate, formatNumber, formatRelative, formatUsd, researchStatusMeta, truncate } from '@/utils/format'

function Card({ label, value, sub, icon: Icon, loading, error }: { label: string; value: string; sub?: string; icon: typeof BarChart3; loading?: boolean; error?: boolean }) {
  return (
    <div className="overview-card">
      <div className="overview-icon"><Icon /></div>
      <p className="metric-label">{label}</p>
      <p className="overview-value">{loading ? '…' : error ? '—' : value}</p>
      <p className="metric-change neutral">{error ? 'No disponible' : sub}</p>
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const total = useResearchCount()
  const completed = useResearchCount('completed')
  const running = useResearchCount('running')
  const pending = useResearchCount('pending')
  const docsIndexed = useDocumentCount('indexed')
  const docsTotal = useDocumentCount()
  const recent = useResearchList({ limit: 100 })

  const items = recent.data?.items ?? []
  const tokens = items.reduce((s, r) => s + r.tokens_input + r.tokens_output, 0)
  const cost = items.reduce((s, r) => s + r.cost_usd, 0)
  const inProgress = (running.data ?? 0) + (pending.data ?? 0)

  return (
    <div className="dashboard-view">
      <div className="dashboard-intro">
        <div>
          <p className="eyebrow">{formatDate(new Date().toISOString())}</p>
          <h1>Panel de investigación</h1>
          <p className="muted-copy">Resumen en tiempo real de tu sistema de investigación multiagente.</p>
        </div>
        <Button className="new-research-button" onClick={() => navigate('/research/new')}><Plus data-icon="inline-start" /> Nueva investigación</Button>
      </div>

      <div className="overview-cards">
        <Card label="Investigaciones" value={formatNumber(total.data ?? 0)} sub={`${formatNumber(completed.data ?? 0)} completadas`} icon={BarChart3} loading={total.isLoading} error={total.isError} />
        <Card label="En progreso" value={formatNumber(inProgress)} sub={`${formatNumber(running.data ?? 0)} en ejecución · ${formatNumber(pending.data ?? 0)} en cola`} icon={Loader2} loading={running.isLoading || pending.isLoading} error={running.isError || pending.isError} />
        <Card label="Documentos indexados" value={formatNumber(docsIndexed.data ?? 0)} sub={`${formatNumber(docsTotal.data ?? 0)} en total`} icon={FileText} loading={docsIndexed.isLoading} error={docsIndexed.isError} />
        <Card label={`Tokens (últimas ${items.length})`} value={formatCompact(tokens)} sub={`${formatUsd(cost)} estimados`} icon={Zap} loading={recent.isLoading} error={recent.isError} />
      </div>

      <div className="dashboard-columns">
        <section className="table-card">
          <div className="card-header">
            <div><h2>Investigaciones recientes</h2><p>Continúa donde lo dejaste.</p></div>
            <Link to="/history" className="link-accent">Ver todas</Link>
          </div>
          {recent.isLoading && <div style={{ paddingTop: 14 }}><LoadingState rows={4} /></div>}
          {recent.isError && <ErrorState error={recent.error} onRetry={() => void recent.refetch()} />}
          {recent.data && items.length === 0 && <EmptyState title="Aún no hay investigaciones" description="Haz tu primera pregunta para ver aquí su progreso." action={<Button size="sm" onClick={() => navigate('/research/new')}>Iniciar investigación</Button>} />}
          {items.slice(0, 5).map((r) => {
            const meta = researchStatusMeta(r.status)
            return (
              <Link to={`/research/${r.id}`} className="research-row" key={r.id}>
                <div className="research-status"><span className={meta.tone === 'live' ? 'status-live' : 'status-complete'} style={meta.tone === 'error' ? { background: '#c9554c' } : meta.tone === 'warn' ? { background: '#d9a441' } : meta.tone === 'idle' ? { background: '#c9c6d3' } : undefined} /></div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold">{truncate(r.query, 90)}</p>
                  <p className="mt-1 truncate text-[11px] text-muted-foreground">{meta.label} · {r.iterations} iter. · {formatCompact(r.tokens_input + r.tokens_output)} tokens</p>
                </div>
                <span className="text-[11px] text-muted-foreground">{formatRelative(r.created_at)}</span>
              </Link>
            )
          })}
        </section>

        <section className="dark-panel quick-card">
          <p className="eyebrow light">Empieza con una pregunta</p>
          <h2 className="mt-3 max-w-[250px] text-2xl font-semibold leading-tight text-white">Convierte la complejidad en claridad.</h2>
          <p className="mt-3 max-w-[280px] text-xs leading-5 text-white/50">Plantea una pregunta compleja. Tus agentes planificarán, investigarán, analizarán y verificarán la respuesta.</p>
          <Button className="mt-8 bg-white text-[#191727] hover:bg-white/90" onClick={() => navigate('/research/new')}><MessageSquarePlus data-icon="inline-start" /> Iniciar investigación</Button>
          <div className="quick-decoration"><div /><div /><div /></div>
        </section>
      </div>
    </div>
  )
}
