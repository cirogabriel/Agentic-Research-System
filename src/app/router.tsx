import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'

/** Cada página se carga bajo demanda: recharts y react-markdown solo se descargan al visitar las vistas que los usan. */
const page = <T extends Record<string, unknown>>(load: () => Promise<T>, name: keyof T): Pick<RouteObject, 'lazy'> => ({
  lazy: async () => ({ Component: (await load())[name] as React.ComponentType }),
})

export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { path: '/', ...page(() => import('@/pages/DashboardPage'), 'DashboardPage') },
      { path: '/research', ...page(() => import('@/pages/MyResearchPage'), 'MyResearchPage') },
      { path: '/research/new', ...page(() => import('@/pages/NewResearchPage'), 'NewResearchPage') },
      { path: '/research/:id', ...page(() => import('@/pages/ResearchPage'), 'ResearchPage') },
      { path: '/history', ...page(() => import('@/pages/HistoryPage'), 'HistoryPage') },
      { path: '/documents', ...page(() => import('@/pages/DocumentsPage'), 'DocumentsPage') },
      { path: '/evaluations', ...page(() => import('@/pages/EvaluationsPage'), 'EvaluationsPage') },
      { path: '/evaluations/:id', ...page(() => import('@/pages/EvaluationDetailPage'), 'EvaluationDetailPage') },
      { path: '/experiments', ...page(() => import('@/pages/ExperimentsPage'), 'ExperimentsPage') },
      { path: '/settings', ...page(() => import('@/pages/SettingsPage'), 'SettingsPage') },
      { path: '/usage', ...page(() => import('@/pages/UsagePage'), 'UsagePage') },
      { path: '*', ...page(() => import('@/pages/NotFoundPage'), 'NotFoundPage') },
    ],
  },
]
export const createAppRouter = () => createBrowserRouter(routes)
