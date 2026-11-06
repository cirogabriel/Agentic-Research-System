import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AlertTriangle, Bell, CircleHelp, Menu, PanelLeftClose, PanelLeftOpen, Plus, Server, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/common/Toaster'
import { apiConfig } from '@/services/api'
import { useConnectionStore } from '@/stores/connectionStore'
import { usePreferencesStore } from '@/stores/preferencesStore'
import { useToastStore } from '@/stores/toastStore'
import { useHealth } from '@/features/settings/queries'
import { formatTime } from '@/utils/format'
import { cn } from '@/utils/cn'
import { activeNavKey, BRAND_ICON, NAV_GROUPS, titleFor } from '../nav'

function docsUrl(): string {
  try {
    return `${new URL(apiConfig.baseUrl, window.location.origin).origin}/docs`
  } catch {
    return '/docs'
  }
}

function Brand() {
  const Icon = BRAND_ICON
  return (
    <div className="flex items-center gap-3 px-5 py-5">
      <div className="brand-mark"><Icon /></div>
      <div>
        <p className="text-sm font-semibold tracking-tight">Agentic Research</p>
        <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Research system</p>
      </div>
    </div>
  )
}

function Sidebar({ collapsed, onToggle, onNavigate }: { collapsed: boolean; onToggle: () => void; onNavigate?: () => void }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const active = activeNavKey(pathname)
  const health = useHealth()
  return (
    <aside className={cn('app-sidebar', collapsed && 'is-collapsed')}>
      <Brand />
      <div className="px-3">
        <Button onClick={() => { navigate('/research/new'); onNavigate?.() }} className="new-research-button w-full justify-start gap-2" size="sm">
          <Plus />{!collapsed && 'Nueva investigación'}
        </Button>
      </div>
      <nav className="mt-7 flex-1 overflow-y-auto px-3" aria-label="Navegación principal">
        {NAV_GROUPS.map((group) => (
          <div className="mb-6" key={group.label}>
            <p className="nav-label">{!collapsed && group.label}</p>
            <div className="flex flex-col gap-1">
              {group.items.map(({ key, label, to, icon: Icon }) => (
                <NavLink key={key} to={to} onClick={onNavigate} className={cn('nav-item', active === key && 'active')} aria-current={active === key ? 'page' : undefined} title={collapsed ? label : undefined}>
                  <Icon />{!collapsed && <span>{label}</span>}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <a className="nav-item" href={docsUrl()} target="_blank" rel="noopener noreferrer" title="Documentación OpenAPI del backend">
          <CircleHelp />{!collapsed && 'Ayuda y recursos'}
        </a>
        <div className="profile-chip" title="Backend conectado">
          <div className="avatar"><Server size={13} /></div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold">Backend ARS</p>
              <p className="truncate text-[10px] text-muted-foreground">{health.data ? `v${health.data.version}` : apiConfig.baseUrl}</p>
            </div>
          )}
        </div>
        <button onClick={onToggle} className="collapse-button" aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}>
          {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
        </button>
      </div>
    </aside>
  )
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const { history, clearHistory } = useToastStore()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button className="icon-button" aria-label="Notificaciones" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Bell />
        {history.length > 0 && <span style={{ position: 'absolute', top: 5, right: 5, width: 7, height: 7, borderRadius: '50%', background: '#8d7cf4' }} />}
      </button>
      {open && (
        <div className="popover" role="region" aria-label="Notificaciones recientes">
          <div className="row" style={{ marginBottom: 6 }}>
            <strong style={{ fontSize: 12 }}>Notificaciones</strong>
            {history.length > 0 && <button className="link-accent spacer" onClick={clearHistory}>Limpiar</button>}
          </div>
          {history.length === 0 && <p className="text-sm-muted">Sin notificaciones en esta sesión.</p>}
          {history.map((n) => (
            <div key={n.id} className={`notif ${n.kind}`}>
              <strong>{n.title}</strong> <span className="text-sm-muted">· {formatTime(new Date(n.at).toISOString())}</span>
              {n.description && <p className="text-sm-muted" style={{ margin: '2px 0 0' }}>{n.description}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SystemStatus() {
  const { data, isError, isLoading } = useHealth()
  const label = isLoading ? 'Comprobando…' : isError ? 'Backend no disponible' : data?.status === 'ok' ? 'Todos los sistemas operativos' : 'Servicio degradado'
  const color = isLoading ? '#c9c6d3' : isError ? '#c9554c' : data?.status === 'ok' ? '#62b491' : '#d9a441'
  return (
    <div className="system-status" role="status">
      <span className="status-dot" style={{ background: color }} /> <span className="hidden sm:inline">{label}</span>
    </div>
  )
}

export function AppLayout() {
  const collapsed = usePreferencesStore((s) => s.sidebarCollapsed)
  const toggle = usePreferencesStore((s) => s.toggleSidebar)
  const authRequired = useConnectionStore((s) => s.authRequired)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { pathname } = useLocation()
  const scrollRef = useRef<HTMLDivElement>(null)
  useEffect(() => { scrollRef.current?.scrollTo({ top: 0 }) }, [pathname])

  return (
    <div className="app-shell">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <div className="app-content">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Abrir menú"><Menu /></button>
          <div className="flex min-w-0 items-center gap-3">
            <div className="breadcrumb-dot" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{titleFor(pathname)}</p>
              <p className="hidden text-[11px] text-muted-foreground sm:block">Workspace / Research operations</p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2 sm:gap-4">
            <SystemStatus />
            <NotificationBell />
          </div>
        </header>
        {mobileOpen && (
          <div className="mobile-sidebar-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setMobileOpen(false) }}>
            <div className="mobile-sidebar">
              <button className="absolute right-4 top-4 icon-button" onClick={() => setMobileOpen(false)} aria-label="Cerrar menú"><X /></button>
              <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} onNavigate={() => setMobileOpen(false)} />
            </div>
          </div>
        )}
        <div className="content-scroll" ref={scrollRef}>
          {authRequired && (
            <div className="banner" role="alert" style={{ margin: '14px 24px 0' }}>
              <AlertTriangle />
              <span>El backend exige una API key. <Link to="/settings" style={{ textDecoration: 'underline', fontWeight: 600 }}>Configúrala aquí</Link>.</span>
            </div>
          )}
          <Outlet />
        </div>
      </div>
      <Toaster />
    </div>
  )
}
