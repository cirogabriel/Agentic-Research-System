import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { researchService } from '@/services/research';
import { notify } from '@/stores/toastStore';
import { toUserMessage } from '@/services/api';
import { isActiveResearch } from '@/utils/format';
import type { ResearchCreate, ResearchOut } from '@/types/api';
import { buildThread } from './thread';

export const researchKeys = {
  all: ['research'] as const,
  list: (p: object) => ['research', 'list', p] as const,
  count: (status?: string) => ['research', 'count', status ?? 'all'] as const,
  detail: (id: string) => ['research', 'detail', id] as const,
  status: (id: string) => ['research', 'status', id] as const,
  report: (id: string) => ['research', 'report', id] as const,
  ancestors: (parentId: string | null | undefined) =>
    ['research', 'ancestors', parentId ?? 'none'] as const,
};

export function useResearchList(
  params: { limit?: number; offset?: number; status?: string } = {},
) {
  return useQuery({
    queryKey: researchKeys.list(params),
    queryFn: ({ signal }) => researchService.list(params, signal),
    placeholderData: (prev) => prev,
  });
}


export function useResearchCount(status?: string) {
  return useQuery({
    queryKey: researchKeys.count(status),
    queryFn: async ({ signal }) =>
      (await researchService.list({ limit: 1, status }, signal)).total,
    refetchInterval: 15_000,
  });
}

export function useResearch(id: string | undefined) {
  return useQuery({
    queryKey: researchKeys.detail(id ?? ''),
    queryFn: ({ signal }) => researchService.get(id!, signal),
    enabled: !!id,
    refetchInterval: (q) =>
      q.state.data && isActiveResearch(q.state.data.status) ? 4000 : false,
  });
}


export function useResearchStatus(id: string | undefined, live: boolean) {
  return useQuery({
    queryKey: researchKeys.status(id ?? ''),
    queryFn: ({ signal }) => researchService.status(id!, signal),
    enabled: !!id,
    refetchInterval: live ? 2500 : false,
  });
}


export function useReport(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: researchKeys.report(id ?? ''),
    queryFn: ({ signal }) => researchService.report(id!, signal),
    enabled: !!id && enabled,
    staleTime: 60_000,
  });
}

async function fetchAncestors(
  parentId: string | null | undefined,
  signal?: AbortSignal,
): Promise<ResearchOut[]> {
  const chain: ResearchOut[] = [];
  let next = parentId;
  while (next && chain.length < 30) {
    const parent = await researchService.get(next, signal);
    chain.unshift(parent);
    next = parent.parent_id;
  }
  return chain;
}


export function useResearchThread(id: string | undefined) {
  const current = useResearch(id);
  const ancestors = useQuery({
    queryKey: researchKeys.ancestors(current.data?.parent_id),
    queryFn: ({ signal }) => fetchAncestors(current.data?.parent_id, signal),
    enabled: !!current.data,
    staleTime: 60_000,
  });
  const all = useResearchList({ limit: 100 });
  const turns =
    current.data && ancestors.data
      ? buildThread(current.data, ancestors.data, all.data?.items ?? [])
      : [];
  return {
    turns,
    isLoading: current.isLoading || ancestors.isLoading,
    error: current.error ?? ancestors.error,
    refetch: () => {
      void current.refetch();
      void ancestors.refetch();
      void all.refetch();
    },
  };
}

export function useCreateResearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ResearchCreate) => researchService.create(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: researchKeys.all });
    },
    onError: (e) =>
      notify.error('No se pudo iniciar la investigación', toUserMessage(e)),
  });
}

export function useClarify(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (answer: string) => researchService.clarify(id, answer),
    onSuccess: () => {
      notify.success('Aclaración enviada', 'La investigación se reanudó.');
      void qc.invalidateQueries({ queryKey: researchKeys.all });
    },
    onError: (e) =>
      notify.error('No se pudo enviar la aclaración', toUserMessage(e)),
  });
}

export function useResume(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => researchService.resume(id),
    onSuccess: () => {
      notify.success(
        'Investigación reanudada',
        'Continúa desde el último checkpoint.',
      );
      void qc.invalidateQueries({ queryKey: researchKeys.all });
    },
    onError: (e) => notify.error('No se pudo reanudar', toUserMessage(e)),
  });
}
