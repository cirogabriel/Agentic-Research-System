import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { AlertTriangle, Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { Toaster } from '@/components/common/Toaster'
import { useConnectionStore } from '@/stores/connectionStore'
import { usePreferencesStore } from '@/stores/preferencesStore'
import { cn } from '@/utils/cn'
import { activeNavKey, BRAND_ICON, NAV_GROUPS, titleFor } from '../nav'

function Brand({ collapsed }: { collapsed: boolean }) {
  const Icon = BRAND_ICON
  return (
    <div className="flex items-center gap-3">

    </div>
  )
}

function Sidebar({ collapsed, onToggle, onNavigate }: { collapsed: boolean; onToggle: () => void; onNavigate?: () => void }) {
  const { pathname } = useLocation()
  const active = activeNavKey(pathname)
  return (
    <aside className={cn('app-sidebar', collapsed && 'is-collapsed')}>
      <div className="sidebar-head">
        <Brand collapsed={collapsed} />
        <button onClick={onToggle} className="collapse-button" aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}>
          {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
        </button>
      </div>
      <nav className="mt-3 flex-1 overflow-y-auto px-3" aria-label="Navegación principal">
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
    </aside>
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
          <p className="truncate text-sm font-normal">{titleFor(pathname)}</p>
        </header>
        {mobileOpen && (
          <div className="mobile-sidebar-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setMobileOpen(false) }}>
            <div className="mobile-sidebar">
    
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
