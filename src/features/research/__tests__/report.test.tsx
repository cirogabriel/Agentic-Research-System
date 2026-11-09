import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders, makeDocument, makeResearch } from '@/test/utils';
import { ReportMessage, UserMessage } from '../ReportViews';
import { TurnView } from '../TurnView';
import type { ReportOut } from '@/types/api';
import { ApiError } from '@/services/api';

vi.mock('@/services/research', () => ({
  researchService: {
    report: vi.fn(),
    clarify: vi.fn(),
    resume: vi.fn(),
    create: vi.fn(),
  },
  fetchReportMarkdown: vi.fn(),
}));
vi.mock('@/services/documents', () => ({ documentsService: { get: vi.fn() } }));
import { researchService } from '@/services/research';
import { documentsService } from '@/services/documents';

const MARKDOWN = `# Causas de los terremotos en los Andes

## Resumen ejecutivo
La subducción de la placa de Nazca es la causa principal [S1].

## Metodología utilizada
Se ejecutaron 1 iteración(es) con 2 subtareas.

## Desarrollo de los hallazgos
| Factor | Efecto |
|---|---|
| Subducción | Alto |

## Conclusiones
- La subducción domina la sismicidad.
`;
const REPORT: ReportOut = {
  research_id: 'r1',
  title: 'Causas de los terremotos en los Andes',
  markdown: MARKDOWN,
  created_at: '2026-11-05T10:02:00Z',
  content: {
    executive_summary:
      'La subducción de la placa de Nazca es la causa principal.',
    conclusions: ['La subducción domina la sismicidad.'],
  },
  quality: {
    evidence_coverage: 0.8,
    citation_validity: 1,
    degraded_report: false,
  },
  sources: [
    {
      label: 'S1',
      document_id: 'd1',
      document_name: 'andes.pdf',
      page_number: 14,
      snippet: 'La placa de Nazca subduce bajo Sudamérica.',
      score: 0.82,
    },
  ],
  findings: [
    {
      statement: 'La placa de Nazca subduce bajo la placa Sudamericana.',
      kind: 'fact',
      aspect: 'Tectónica',
      support_level: 'supported',
      verification_note: null,
      sources: ['S1'],
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(documentsService.get).mockResolvedValue(makeDocument());
});

describe('ReportMessage', () => {
  it('muestra título, resumen, hallazgos, conclusión y fuentes con metadatos reales del documento', async () => {
    vi.mocked(researchService.report).mockResolvedValue(REPORT);
    renderWithProviders(<ReportMessage turn={makeResearch()} />);
    expect(
      await screen.findByRole('heading', {
        name: 'Causas de los terremotos en los Andes',
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Respaldado')).toBeInTheDocument();
    expect(screen.getByText('Tectónica')).toBeInTheDocument();
    expect(
      screen.getByText('Conclusión de la investigación'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Verificada · cobertura 80%/)).toBeInTheDocument();
    expect(
      await screen.findByText('Seismicity and the Andes'),
    ).toBeInTheDocument();
    expect(await screen.findByText(/J\. Ramos/)).toBeInTheDocument();
    expect(screen.getByText(/pág\. 14/)).toBeInTheDocument();
  });

  it('el fragmento original se consulta bajo demanda', async () => {
    vi.mocked(researchService.report).mockResolvedValue(REPORT);
    renderWithProviders(<ReportMessage turn={makeResearch()} />);
    await screen.findByText('Seismicity and the Andes');
    expect(
      screen.queryByText('La placa de Nazca subduce bajo Sudamérica.'),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole('button', { name: /ver fragmento de S1/i }),
    );
    expect(
      screen.getByText('La placa de Nazca subduce bajo Sudamérica.'),
    ).toBeInTheDocument();
  });

  it('el informe completo renderiza secciones, tablas Markdown y citas enlazadas a la fuente', async () => {
    vi.mocked(researchService.report).mockResolvedValue(REPORT);
    renderWithProviders(<ReportMessage turn={makeResearch()} />);
    await screen.findByText('Seismicity and the Andes');
    await userEvent.click(
      screen.getByRole('button', { name: /ver informe completo/i }),
    );
    expect(
      screen.getByRole('heading', { name: 'Metodología utilizada' }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('table')).toHaveLength(2); // tabla Markdown + tabla de hallazgos
    expect(
      screen.getByRole('cell', { name: 'Subducción' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /hallazgos verificados/i }),
    ).toBeInTheDocument();
    const cite = screen.getByRole('link', { name: '[S1]' });
    await userEvent.click(cite);
    expect(document.getElementById('doc-r1-S1')).toHaveClass('is-target');
  });

  it('muestra un estado de error con reintento si el informe no carga', async () => {
    vi.mocked(researchService.report)
      .mockRejectedValueOnce(
        new ApiError('server', 'El servidor encontró un error.', 500),
      )
      .mockResolvedValue(REPORT);
    renderWithProviders(<ReportMessage turn={makeResearch()} />);
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/No se pudo cargar el informe/);
    await userEvent.click(
      within(alert).getByRole('button', { name: /reintentar/i }),
    );
    expect(
      await screen.findByRole('heading', {
        name: 'Causas de los terremotos en los Andes',
      }),
    ).toBeInTheDocument();
  });
});

describe('mensajes y estados del turno', () => {
  it('muestra el mensaje del usuario con su hora', () => {
    renderWithProviders(
      <UserMessage
        turn={makeResearch({ query: 'Profundiza en la subducción de Nazca' })}
      />,
    );
    expect(
      screen.getByText('Profundiza en la subducción de Nazca'),
    ).toBeInTheDocument();
    expect(screen.getByText(/^Tú ·/)).toBeInTheDocument();
  });

  it('aclaración: lista las preguntas y envía la respuesta al endpoint real', async () => {
    vi.mocked(researchService.clarify).mockResolvedValue(
      makeResearch({ status: 'pending' }),
    );
    renderWithProviders(
      <TurnView
        turn={makeResearch({
          status: 'needs_clarification',
          clarification_questions: ['¿Qué región?', '¿Qué periodo?'],
        })}
      />,
    );
    expect(screen.getByText('¿Qué región?')).toBeInTheDocument();
    await userEvent.type(
      screen.getByLabelText('Tu respuesta'),
      'Chile, 2010-2020',
    );
    await userEvent.click(
      screen.getByRole('button', { name: /enviar aclaración/i }),
    );
    await waitFor(() =>
      expect(researchService.clarify).toHaveBeenCalledWith(
        'r1',
        'Chile, 2010-2020',
      ),
    );
  });

  it('fallo: ofrece reanudar y no expone detalles internos', async () => {
    vi.mocked(researchService.resume).mockResolvedValue(
      makeResearch({ status: 'running' }),
    );
    renderWithProviders(
      <TurnView
        turn={makeResearch({ status: 'failed', stop_reason: 'error' })}
      />,
    );
    expect(screen.getByText(/no pudo completarse/i)).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /reanudar/i }));
    await waitFor(() =>
      expect(researchService.resume).toHaveBeenCalledWith('r1'),
    );
  });
});
