import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { evaluationsService } from '@/services/evaluations';
import { isApiError, toUserMessage } from '@/services/api';
import { notify } from '@/stores/toastStore';
import type { DatasetCreate, EvaluationCreate } from '@/types/api';

export const evalKeys = {
  all: ['evaluations'] as const,
  datasets: ['evaluations', 'datasets'] as const,
  list: (p: object) => ['evaluations', 'list', p] as const,
  detail: (id: string) => ['evaluations', 'detail', id] as const,
  compare: (p: object) => ['evaluations', 'compare', p] as const,
};
const active = (s?: string) => s === 'pending' || s === 'running';

export const useDatasets = () =>
  useQuery({
    queryKey: evalKeys.datasets,
    queryFn: ({ signal }) => evaluationsService.datasets(signal),
  });

export function useEvaluations(
  params: { limit?: number; offset?: number; dataset_id?: string } = {},
) {
  return useQuery({
    queryKey: evalKeys.list(params),
    queryFn: ({ signal }) => evaluationsService.list(params, signal),
    placeholderData: (prev) => prev,
    refetchInterval: (q) =>
      q.state.data?.items.some((e) => active(e.status)) ? 4000 : false,
  });
}

export function useEvaluation(id: string | undefined) {
  return useQuery({
    queryKey: evalKeys.detail(id ?? ''),
    queryFn: ({ signal }) => evaluationsService.get(id!, signal),
    enabled: !!id,
    refetchInterval: (q) => (active(q.state.data?.status) ? 4000 : false),
  });
}

/** 409 = menos de 2 experimentos completados: no es un fallo, es "sin datos suficientes". */
export function useComparison(
  params: { experiment_ids?: string[]; dataset_id?: string },
  enabled = true,
) {
  return useQuery({
    queryKey: evalKeys.compare(params),
    queryFn: ({ signal }) => evaluationsService.compare(params, signal),
    enabled,
    retry: false,
  });
}
export const isInsufficientData = (e: unknown) =>
  isApiError(e) && e.kind === 'conflict';

export function useCreateDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: DatasetCreate) => evaluationsService.createDataset(b),
    onSuccess: (d) => {
      notify.success('Dataset creado', d.name);
      void qc.invalidateQueries({ queryKey: evalKeys.datasets });
    },
    onError: (e) =>
      notify.error('No se pudo crear el dataset', toUserMessage(e)),
  });
}

export function useCreateEvaluation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: EvaluationCreate) => evaluationsService.create(b),
    onSuccess: (e) => {
      notify.success(
        'Experimento lanzado',
        `${e.name} se ejecuta en segundo plano.`,
      );
      void qc.invalidateQueries({ queryKey: evalKeys.all });
    },
    onError: (e) =>
      notify.error('No se pudo lanzar el experimento', toUserMessage(e)),
  });
}
