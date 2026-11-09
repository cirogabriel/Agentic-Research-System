import {
  BrainCircuit,
  Clock3,
  FileText,
  LayoutDashboard,
  MessageSquarePlus,
  Settings2,
  Zap,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  key: string;
  label: string;
  to: string;
  icon: LucideIcon;
  title: string;
}
export interface NavGroup {
  label: string;
  items: NavItem[];
}


export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Principal',
    items: [
      {
        key: 'dashboard',
        label: 'Dashboard',
        to: '/dashboard',
        icon: LayoutDashboard,
        title: 'Dashboard',
      },
      {
        key: 'new',
        label: 'Nueva investigación',
        to: '/research/new',
        icon: MessageSquarePlus,
        title: 'Nueva investigación',
      },

      {
        key: 'history',
        label: 'Historial',
        to: '/history',
        icon: Clock3,
        title: 'Historial',
      },
    ],
  },
  {
    label: 'Conocimiento',
    items: [
      {
        key: 'documents',
        label: 'Documentos',
        to: '/documents',
        icon: FileText,
        title: 'Documentos',
      },
    ],
  },

  /*{ label: 'Análisis', items: [
    { key: 'evaluations', label: 'Evaluaciones', to: '/evaluations', icon: Gauge, title: 'Evaluaciones' },
    { key: 'experiments', label: 'Experimentos', to: '/experiments', icon: SlidersHorizontal, title: 'Experimentos comparativos' },
  ] },

  */
  {
    label: 'Sistema',
    items: [
      {
        key: 'settings',
        label: 'Configuración',
        to: '/settings',
        icon: Settings2,
        title: 'Configuración',
      },
      {
        key: 'usage',
        label: 'Modelos y consumo',
        to: '/usage',
        icon: Zap,
        title: 'Modelos y consumo',
      },
    ],
  },
];

export const BRAND_ICON = BrainCircuit;

export function activeNavKey(pathname: string): string | null {
  if (pathname === '/dashboard') return 'dashboard';
  if (pathname === '/research/new') return 'new';
  if (pathname === '/research' || pathname.startsWith('/research/'))
    return 'history';
  if (pathname.startsWith('/history')) return 'history';
  if (pathname.startsWith('/documents')) return 'documents';
  if (pathname.startsWith('/evaluations')) return 'evaluations';
  if (pathname.startsWith('/experiments')) return 'experiments';
  if (pathname.startsWith('/settings')) return 'settings';
  if (pathname.startsWith('/usage')) return 'usage';
  return null;
}

export function titleFor(pathname: string): string {
  if (/^\/research\/[^/]+$/.test(pathname) && pathname !== '/research/new')
    return 'Investigación';
  if (/^\/evaluations\/[^/]+$/.test(pathname)) return 'Detalle de evaluación';
  const key = activeNavKey(pathname);
  return (
    NAV_GROUPS.flatMap((g) => g.items).find((i) => i.key === key)?.title ??
    'Agentic Research'
  );
}
