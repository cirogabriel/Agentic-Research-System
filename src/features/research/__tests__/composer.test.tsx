import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route } from 'react-router-dom';
import { renderWithProviders } from '@/test/utils';
import { NewResearchPage } from '@/pages/NewResearchPage';
import { ResearchComposer } from '../ResearchComposer';
import { buildOptions, validateDefaults, validateQuery } from '../options';
import { INITIAL_DEFAULTS } from '@/stores/preferencesStore';
import { ApiError } from '@/services/api';

vi.mock('@/services/research', () => ({
  researchService: { create: vi.fn() },
  fetchReportMarkdown: vi.fn(),
}));
vi.mock('@/services/system', () => ({
  systemService: {
    configuration: vi
      .fn()
      .mockResolvedValue({
        max_iterations: 3,
        token_budget: 60000,
        retrieval_top_k: 5,
      }),
    health: vi.fn(),
  },
}));
vi.mock('@/services/documents', () => ({
  documentsService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}));
import { researchService } from '@/services/research';

beforeEach(() => vi.clearAllMocks());

describe('options', () => {
  it('solo envía los parámetros fijados por el usuario', () => {
    expect(buildOptions(INITIAL_DEFAULTS, [])).toEqual({
      parallel: true,
      reinvestigate: true,
    });
    expect(
      buildOptions(
        { ...INITIAL_DEFAULTS, top_k: 8, retrieval_strategy: 'hybrid' },
        ['d1'],
      ),
    ).toEqual({
      parallel: true,
      reinvestigate: true,
      top_k: 8,
      retrieval_strategy: 'hybrid',
      document_ids: ['d1'],
    });
  });
  it('valida rangos y longitud como el backend', () => {
    expect(
      validateDefaults({
        ...INITIAL_DEFAULTS,
        max_iterations: 11,
        token_budget: 100,
      }),
    ).toHaveProperty('max_iterations');
    expect(
      validateDefaults({ ...INITIAL_DEFAULTS, max_iterations: 5 }),
    ).toEqual({});
    expect(validateQuery('abc')).toMatch(/al menos/);
    expect(validateQuery('x'.repeat(4001))).toMatch(/superar/);
    expect(validateQuery('Una pregunta válida')).toBeNull();
  });
});

describe('ResearchComposer', () => {
  it('muestra error de validación y no envía preguntas demasiado cortas', async () => {
    const onSubmit = vi.fn();
    renderWithProviders(
      <ResearchComposer placeholder="Pregunta" onSubmit={onSubmit} />,
    );
    const box = screen.getByRole('textbox', {
      name: /pregunta de investigación/i,
    });
    await userEvent.type(box, 'abc');
    await userEvent.tab();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /al menos 5 caracteres/,
    );
    expect(screen.getByRole('button', { name: /enviar/i })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('envía con Enter y limpia el campo; Shift+Enter no envía', async () => {
    const onSubmit = vi.fn();
    renderWithProviders(
      <ResearchComposer placeholder="Pregunta" onSubmit={onSubmit} />,
    );
    const box = screen.getByRole('textbox', {
      name: /pregunta de investigación/i,
    });
    await userEvent.type(
      box,
      'Compara las teorías sobre la subducción{Shift>}{Enter}{/Shift}',
    );
    expect(onSubmit).not.toHaveBeenCalled();
    await userEvent.type(box, '{Enter}');
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0]![0]).toContain('subducción');
    expect(box).toHaveValue('');
  });

  it('queda deshabilitado y explica el motivo', () => {
    renderWithProviders(
      <ResearchComposer
        placeholder="Pregunta"
        disabledReason="La investigación está en curso."
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('textbox')).toHaveAttribute(
      'placeholder',
      'La investigación está en curso.',
    );
  });
});

describe('NewResearchPage', () => {
  it('crea la investigación en POST /research y navega a su conversación', async () => {
    vi.mocked(researchService.create).mockResolvedValue({
      id: 'nuevo-1',
      parent_id: null,
      query: 'q',
      status: 'pending',
      iterations: 0,
      tokens_input: 0,
      tokens_output: 0,
      cost_usd: 0,
      created_at: '2026-11-05T10:00:00Z',
    });
    renderWithProviders(<NewResearchPage />, {
      route: '/research/new',
      path: '/research/new',
      extraRoutes: (
        <Route path="/research/:id" element={<p>Conversación abierta</p>} />
      ),
    });
    await userEvent.type(
      screen.getByRole('textbox'),
      'Investiga las principales causas de los terremotos en los Andes{Enter}',
    );
    await waitFor(() => expect(researchService.create).toHaveBeenCalled());
    expect(vi.mocked(researchService.create).mock.calls[0]![0]).toEqual({
      query: 'Investiga las principales causas de los terremotos en los Andes',
      options: { parallel: true, reinvestigate: true },
    });
    expect(await screen.findByText('Conversación abierta')).toBeInTheDocument();
  });

  it('muestra un error comprensible y permanece en la página si el backend falla', async () => {
    vi.mocked(researchService.create).mockRejectedValue(
      new ApiError('network', 'No se pudo conectar con el backend.'),
    );
    renderWithProviders(<NewResearchPage />, {
      route: '/research/new',
      path: '/research/new',
    });
    await userEvent.type(
      screen.getByRole('textbox'),
      'Una pregunta de prueba válida{Enter}',
    );
    await waitFor(() => expect(researchService.create).toHaveBeenCalled());
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });
});
