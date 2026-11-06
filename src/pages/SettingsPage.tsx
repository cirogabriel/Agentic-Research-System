import { useEffect, useState, Fragment } from 'react'
import { CheckCircle2, KeyRound, Lock, Plug, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/components/common/States'
import { OptionsForm } from '@/features/research/OptionsForm'
import { validateDefaults } from '@/features/research/options'
import { CONFIG_GROUPS, HIDDEN_KEYS, formatConfigValue } from '@/features/settings/catalog'
import { useConfiguration, useHealth } from '@/features/settings/queries'
import { apiConfig } from '@/services/api'
import { useConnectionStore } from '@/stores/connectionStore'
import { INITIAL_DEFAULTS, usePreferencesStore, type ResearchDefaults } from '@/stores/preferencesStore'
import { notify } from '@/stores/toastStore'

function ConnectionPanel() {
  const { apiKey, setApiKey } = useConnectionStore()
  const [draft, setDraft] = useState(apiKey ?? '')
  const health = useHealth()
  const config = useConfiguration()
  const keyMode = config.data?.api_key
  return (
    <section className="panel" aria-labelledby="conn-h">
      <div className="row"><Plug size={15} /><h2 id="conn-h">Conexión</h2><span className="lock-tag spacer">{`VITE_API_BASE_URL`}</span></div>
      <p className="panel-sub">URL del backend: <span className="mono">{apiConfig.baseUrl}</span> (se define al construir la app).</p>
      <div className="row-wrap" style={{ margin: '12px 0' }}>
        {health.isLoading ? <span className="spinner" /> : health.isError ? <XCircle size={16} color="#b4423a" /> : <CheckCircle2 size={16} color="#3f8a63" />}
        <span style={{ fontSize: 12 }}>{health.isLoading ? 'Comprobando…' : health.isError ? 'No se pudo contactar con el backend' : `Backend ${health.data?.status === 'ok' ? 'operativo' : 'degradado'} · v${health.data?.version}`}</span>
        <Button size="xs" variant="outline" className="spacer" onClick={() => { void health.refetch(); void config.refetch() }}>Probar conexión</Button>
      </div>
      {health.data && Object.keys(health.data.checks).length > 0 && <p className="hint">{Object.entries(health.data.checks).map(([k, v]) => `${k}: ${String(v)}`).join(' · ')}</p>}
      <div className="field" style={{ marginTop: 12, maxWidth: 420 }}>
        <label htmlFor="api-key"><KeyRound size={11} style={{ display: 'inline' }} /> API key del backend {keyMode === 'configured' ? '(requerida por el backend)' : keyMode === 'disabled' ? '(el backend no la exige)' : ''}</label>
        <input id="api-key" className="input" type="password" autoComplete="off" value={draft} placeholder="X-API-Key" onChange={(e) => setDraft(e.target.value)} />
        <span className="hint">Se guarda solo en esta pestaña (sessionStorage). Nunca se incluye en el código ni se envía a terceros.</span>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <Button size="sm" onClick={() => { setApiKey(draft.trim() || null); notify.success('API key guardada'); void config.refetch() }}>Guardar</Button>
        {apiKey && <Button size="sm" variant="outline" onClick={() => { setApiKey(null); setDraft(''); notify.info('API key eliminada') }}>Quitar</Button>}
      </div>
    </section>
  )
}

function DefaultsPanel() {
  const stored = usePreferencesStore((s) => s.defaults)
  const setDefaults = usePreferencesStore((s) => s.setDefaults)
  const config = useConfiguration()
  const [draft, setDraft] = useState<ResearchDefaults>(stored)
  useEffect(() => setDraft(stored), [stored])
  const errors = validateDefaults(draft)
  const invalid = Object.keys(errors).length > 0
  return (
    <section className="panel" aria-labelledby="def-h">
      <div className="row"><h2 id="def-h">Valores por defecto de nuevas investigaciones</h2><span className="edit-tag spacer">Modificable</span></div>
      <p className="panel-sub">El backend permite ajustar estos parámetros por solicitud (campo <span className="mono">options</span>). Se guardan en este navegador y se envían al lanzar cada investigación; los campos vacíos usan el valor del backend.</p>
      <div style={{ marginTop: 14 }}>
        <OptionsForm value={draft} onChange={setDraft} idPrefix="settings" backend={{ max_iterations: config.data?.max_iterations, token_budget: config.data?.token_budget, retrieval_top_k: config.data?.retrieval_top_k }} />
      </div>
      <div className="row" style={{ marginTop: 14 }}>
        <Button size="sm" disabled={invalid} onClick={() => { setDefaults(draft); notify.success('Valores por defecto guardados') }}>Guardar</Button>
        <Button size="sm" variant="outline" onClick={() => { setDraft(INITIAL_DEFAULTS); setDefaults(INITIAL_DEFAULTS); notify.info('Valores restablecidos') }}>Restablecer</Button>
      </div>
    </section>
  )
}

function BackendConfigPanel() {
  const { data, isLoading, error, refetch } = useConfiguration()
  if (isLoading) return <section className="panel"><LoadingState rows={4} /></section>
  if (error || !data) return <section className="panel"><ErrorState error={error} onRetry={() => void refetch()} /></section>
  const grouped = new Set(CONFIG_GROUPS.flatMap((g) => g.keys))
  const others = Object.keys(data).filter((k) => !grouped.has(k) && !HIDDEN_KEYS.has(k))
  const groups = [...CONFIG_GROUPS, ...(others.length ? [{ title: 'Otros', keys: others }] : [])]
  return (
    <section className="panel" aria-labelledby="be-h">
      <div className="row"><Lock size={14} /><h2 id="be-h">Configuración del backend</h2><span className="lock-tag spacer">Solo lectura</span></div>
      <p className="panel-sub">Estos valores se definen únicamente en el backend mediante variables de entorno (archivo <span className="mono">.env</span>) y requieren reiniciar el servicio. El backend no ofrece un endpoint para modificarlos.</p>
      <div className="stack" style={{ marginTop: 14 }}>
        {groups.map((g) => {
          const keys = g.keys.filter((k) => k in data)
          if (!keys.length) return null
          return (
            <div key={g.title}>
              <p className="eyebrow" style={{ marginBottom: 8 }}>{g.title}</p>
              <dl className="kv" style={{ gridTemplateColumns: '220px 1fr' }}>
                {keys.map((k) => <Fragment key={k}><dt><span className="env-tag">{k.toUpperCase()}</span></dt><dd>{formatConfigValue(data[k])}</dd></Fragment>)}
              </dl>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export function SettingsPage() {
  return (
    <div className="page" style={{ maxWidth: 940 }}>
      <div className="page-header"><div><p className="eyebrow">Sistema</p><h1>Configuración</h1><p className="muted-copy">Qué puedes cambiar desde aquí y qué solo se controla en el backend.</p></div></div>
      <div className="stack"><ConnectionPanel /><DefaultsPanel /><BackendConfigPanel /></div>
    </div>
  )
}
