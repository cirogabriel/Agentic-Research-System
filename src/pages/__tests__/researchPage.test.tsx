import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderWithProviders, makeResearch } from '@/test/utils'
import { ResearchPage } from '../ResearchPage'
import type { SseMessage } from '@/services/api/sse'

vi.mock('@/services/research', () => ({
  researchService: { get: vi.fn(), list: vi.fn(), status: vi.fn(), report: vi.fn(), create: vi.fn(), clarify: vi.fn(), resume: vi.fn() }, fetchReportMarkdown: vi.fn(),
}))
vi.mock('@/services/system', () => ({ systemService: { configuration: vi.fn().mockResolvedValue({}), health: vi.fn() } }))
vi.mock('@/services/documents', () => ({ documentsService: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }), get: vi.fn() } }))
vi.mock('@/services/api', async (orig) => ({ ...(await orig<typeof import('@/services/api')>()), connectResearchEvents: vi.fn() }))
import { researchService } from '@/services/research'
import { connectResearchEvents } from '@/services/api'

const ev = (id: number, type: string, message: string, payload: object = {}): SseMessage => ({ id: String(id), event: type, data: JSON.stringify({ type, message, payload, at: '2026-11-05T10:00:0' + id + 'Z' }) })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(researchService.list).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(researchService.status).mockResolvedValue({ id: 'r1', status: 'running', iteration: 1, tokens_input: 500, tokens_output: 120, embedding_tokens: 80, cost_usd: 0.0002 })
})

describe('ResearchPage', () => {
  it('muestra la conversación y el progreso derivado de los eventos SSE reales', async () => {
    vi.mocked(researchService.get).mockResolvedValue(makeResearch({ status: 'running', finished_at: null }))
    vi.mocked(connectResearchEvents).mockReturnValue(async (o) => {
      o.onOpen()
      o.onMessage(ev(1, 'research.started', 'Investigación iniciada'))
      o.onMessage(ev(2, 'query.analyzed', 'Consulta analizada'))
      o.onMessage(ev(3, 'plan.created', '2 subtarea(s) planificada(s)', { rationale: 'Dividir por causas', tasks: ['Causas', 'Comparación'] }))
      o.onMessage(ev(4, 'task.started', 'Buscando: Causas'))
      await new Promise(() => {}) // el stream sigue abierto
    })
    renderWithProviders(<ResearchPage />, { route: '/research/r1', path: '/research/:id' })

    // mensaje del usuario y estado en curso
    expect(await screen.findAllByText(/Investiga las causas de los terremotos en los Andes/)).not.toHaveLength(0)
    const panel = await screen.findByRole('region', { name: /actividad de agentes/i })
    expect(await within(panel).findByText(/Buscando: Causas/)).toBeInTheDocument()
    expect(within(panel).getByText(/Supervisor Agent/)).toBeInTheDocument()

    // panel oscuro: Planificación completada, Investigación activa
    const progress = screen.getByRole('region', { name: /progreso de la investigación/i })
    const rows = Array.from(progress.querySelectorAll('.stage-row'))
    const byLabel = (l: string) => rows.find((r) => r.textContent?.includes(l))!
    expect(byLabel('Planificación')).toHaveClass('done')
    expect(byLabel('Investigación')).toHaveClass('current')
    expect(byLabel('Verificación')).not.toHaveClass('done')
    expect(await screen.findByText('EN VIVO')).toBeInTheDocument()

    // el seguimiento queda deshabilitado mientras corre
    expect(screen.getByRole('textbox', { name: /pregunta de investigación/i })).toBeDisabled()
    expect(await screen.findByText(/Subtareas: 0\/1 completadas/)).toBeInTheDocument()
  })

  it('reconstruye el hilo con los turnos de seguimiento (parent_id)', async () => {
    const root = makeResearch({ id: 'r0', query: 'Primera consulta sobre los Andes' })
    const child = makeResearch({ id: 'r1', parent_id: 'r0', query: 'Profundiza en la subducción de Nazca', status: 'failed' })
    vi.mocked(researchService.get).mockImplementation(async (id: string) => (id === 'r0' ? root : child))
    vi.mocked(researchService.report).mockRejectedValue(new Error('sin informe'))
    vi.mocked(connectResearchEvents).mockReturnValue(async (o) => { o.onOpen(); o.onMessage({ event: 'end', data: '{}' }) })
    renderWithProviders(<ResearchPage />, { route: '/research/r1', path: '/research/:id' })
    expect((await screen.findAllByText('Primera consulta sobre los Andes')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Profundiza en la subducción de Nazca').length).toBeGreaterThan(0)
    expect(screen.getByText(/Conversación · 2 turnos/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reanudar/i })).toBeInTheDocument()
  })

  it('error si la investigación no existe', async () => {
    const { ApiError } = await import('@/services/api')
    vi.mocked(researchService.get).mockRejectedValue(new ApiError('not_found', 'Investigación no encontrada', 404))
    vi.mocked(connectResearchEvents).mockReturnValue(async () => {})
    renderWithProviders(<ResearchPage />, { route: '/research/zzz', path: '/research/:id' })
    expect(await screen.findByText('La investigación no existe')).toBeInTheDocument()
  })
})
