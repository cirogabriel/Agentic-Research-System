import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/utils';
import { formatByKind, getMetric, resolveGroups, unflatten } from '../metrics';
import { parseDatasetJson } from '../DatasetForm';
import { ExperimentsPage } from '@/pages/ExperimentsPage';
import { ApiError } from '@/services/api';

vi.mock('@/services/evaluations', () => ({
  evaluationsService: {
    datasets: vi.fn(),
    list: vi.fn(),
    compare: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    createDataset: vi.fn(),
  },
}));
import { evaluationsService } from '@/services/evaluations';

const SUMMARY = {
  retrieval: {
    'recall@1': 0.5,
    'recall@3': 0.8,
    'precision@1': 0.5,
    'precision@3': 0.4,
    mrr: 0.7,
    'ndcg@1': 0.5,
    'ndcg@3': 0.7,
    retrieval_latency_ms: 120,
  },
  generation: { faithfulness_lexical: 0.9, answer_correctness_f1: 0.6 },
  agent: {
    task_completion_rate: 1,
    evidence_coverage: 0.8,
    iterations_per_task: 1.5,
    agent_failure_rate: 0,
    latency_ms_mean: 5200,
    tokens_input_total: 9000,
    tokens_output_total: 2000,
  },
  cost: {
    tokens_total: 11000,
    cost_usd_total: 0.0025,
    cost_usd_per_item: 0.0005,
  },
  meta: { items_total: 5, items_failed: 0 },
};

describe('metrics', () => {
  it('agrupa solo las métricas presentes y expande @K dinámicamente', () => {
    const groups = resolveGroups(SUMMARY);
    expect(groups.map((g) => g.title)).toEqual([
      'Recuperación',
      'Generación',
      'Agentes',
      'Rendimiento',
    ]);
    const labels = groups[0]!.metrics.map((m) => m.label);
    expect(labels).toContain('Recall@3');
    expect(labels).toContain('NDCG@1');
    expect(labels).toContain('MRR');
    expect(labels).not.toContain('Recall@5');
    expect(groups[1]!.metrics.map((m) => m.label)).toEqual([
      'Faithfulness',
      'Answer Correctness',
    ]);
    expect(resolveGroups({ retrieval: { mrr: 1 } }).map((g) => g.id)).toEqual([
      'retrieval',
    ]);
    expect(resolveGroups(null)).toEqual([]);
  });
  it('lee métricas y formatea por tipo; unflatten invierte el flatten del backend', () => {
    expect(getMetric(SUMMARY, 'agent.latency_ms_mean')).toBe(5200);
    expect(getMetric(SUMMARY, 'agent.nope')).toBeUndefined();
    expect(formatByKind(5200, 'ms')).toBe('5.20 s');
    expect(formatByKind(0.0025, 'usd')).toBe('$0.00250');
    expect(unflatten({ 'retrieval.mrr': 1, 'cost.tokens_total': 5 })).toEqual({
      retrieval: { mrr: 1 },
      cost: { tokens_total: 5 },
    });
  });
});

describe('parseDatasetJson', () => {
  const item = {
    id: 'q1',
    question: '¿Qué es la subducción?',
    relevant_documents: ['andes.pdf'],
  };
  it('acepta {name, items} o una lista de ítems', () => {
    const a = parseDatasetJson(
      JSON.stringify({ name: 'ds', items: [item] }),
      'x',
    );
    expect(a.ok && a.data.items[0]!.expected_keywords).toEqual([]);
    const b = parseDatasetJson(JSON.stringify([item]), 'archivo');
    expect(b.ok && b.data.name).toBe('archivo');
  });
  it('rechaza JSON inválido, listas vacías e ítems incompletos', () => {
    expect(parseDatasetJson('{no', 'x')).toMatchObject({
      ok: false,
      error: expect.stringMatching(/JSON válido/),
    });
    expect(parseDatasetJson('[]', 'x')).toMatchObject({ ok: false });
    expect(parseDatasetJson(JSON.stringify([{ id: 'a' }]), 'x')).toMatchObject({
      ok: false,
      error: expect.stringMatching(/question/),
    });
  });
});

describe('ExperimentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(evaluationsService.datasets).mockResolvedValue([]);
    vi.mocked(evaluationsService.list).mockResolvedValue({
      items: [],
      total: 0,
    });
  });
  it('explica la falta de datos cuando el backend responde 409 (menos de 2 experimentos)', async () => {
    vi.mocked(evaluationsService.compare).mockRejectedValue(
      new ApiError(
        'conflict',
        'Se necesitan al menos 2 experimentos completados para comparar',
        409,
      ),
    );
    renderWithProviders(<ExperimentsPage />);
    expect(
      await screen.findByText('Aún no hay datos suficientes'),
    ).toBeInTheDocument();
  });
  it('compara A/B/C con deltas respecto a la base, sin inventar métricas ausentes', async () => {
    vi.mocked(evaluationsService.compare).mockResolvedValue({
      baseline_id: 'a',
      experiments: [
        {
          id: 'a',
          name: 'base',
          mode: 'A',
          dataset_id: 'd',
          metrics: { 'retrieval.mrr': 0.6, 'cost.cost_usd_total': 0.001 },
        },
        {
          id: 'c',
          name: 'multiagente',
          mode: 'C',
          dataset_id: 'd',
          metrics: {
            'retrieval.mrr': 0.8,
            'cost.cost_usd_total': 0.004,
            'agent.evidence_coverage': 0.9,
          },
        },
      ],
      deltas: {
        c: {
          'retrieval.mrr': 0.2,
          'cost.cost_usd_total': 0.003,
          'agent.evidence_coverage': null,
        },
      },
    });
    renderWithProviders(<ExperimentsPage />);
    expect(await screen.findByText('A · RAG convencional')).toBeInTheDocument();
    expect(
      screen.getByText('C · RAG multiagente con verificación'),
    ).toBeInTheDocument();
    expect(screen.getByText('+0.2')).toBeInTheDocument();
    const cov = screen.getByRole('row', { name: /Evidence Coverage/ });
    expect(cov).toHaveTextContent('—'); // no existe en la configuración A
    await waitFor(() =>
      expect(evaluationsService.compare).toHaveBeenCalledWith(
        { dataset_id: undefined },
        expect.anything(),
      ),
    );
  });
  it('en modo manual exige al menos dos experimentos antes de consultar', async () => {
    vi.mocked(evaluationsService.list).mockResolvedValue({
      items: [
        {
          id: 'e1',
          name: 'uno',
          dataset_id: 'd',
          mode: 'A',
          config: {},
          status: 'completed',
          summary: {},
          error: null,
          created_at: '2026-11-05T10:00:00Z',
          finished_at: null,
        },
      ],
      total: 1,
    });
    vi.mocked(evaluationsService.compare).mockRejectedValue(
      new ApiError('conflict', 'x', 409),
    );
    renderWithProviders(<ExperimentsPage />);
    await userEvent.click(
      screen.getByRole('button', { name: /elegir experimentos/i }),
    );
    expect(
      await screen.findByText('Selecciona al menos 2 experimentos.'),
    ).toBeInTheDocument();
    expect(
      vi
        .mocked(evaluationsService.compare)
        .mock.calls.every(([p]) => !p.experiment_ids),
    ).toBe(true);
  });
});
