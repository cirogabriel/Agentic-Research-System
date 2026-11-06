import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { documentsService } from '@/services/documents'
import { toUserMessage } from '@/services/api'
import { notify } from '@/stores/toastStore'

export const documentKeys = {
  all: ['documents'] as const,
  list: (p: object) => ['documents', 'list', p] as const,
  count: (status?: string) => ['documents', 'count', status ?? 'all'] as const,
  detail: (id: string) => ['documents', 'detail', id] as const,
}

export function useDocuments(params: { limit: number; offset: number; status?: string; file_type?: string }) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: ({ signal }) => documentsService.list(params, signal),
    placeholderData: (prev) => prev,
    // Mientras haya documentos en "processing" se sondea: la indexación ocurre en segundo plano.
    refetchInterval: (q) => (q.state.data?.items.some((d) => d.status === 'processing') ? 3000 : false),
  })
}

export function useDocumentCount(status?: string) {
  return useQuery({
    queryKey: documentKeys.count(status),
    queryFn: async ({ signal }) => (await documentsService.list({ limit: 1, status }, signal)).total,
    refetchInterval: 15_000,
  })
}

export function useDocument(id: string | null) {
  return useQuery({ queryKey: documentKeys.detail(id ?? ''), queryFn: ({ signal }) => documentsService.get(id!, signal), enabled: !!id, staleTime: 30_000 })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => documentsService.remove(id),
    onSuccess: () => { notify.success('Documento eliminado'); void qc.invalidateQueries({ queryKey: documentKeys.all }) },
    onError: (e) => notify.error('No se pudo eliminar el documento', toUserMessage(e)),
  })
}

export function useReindexDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) => documentsService.reindex(id, force),
    onSuccess: (r) => {
      if (r.action === 'up_to_date') notify.info('El documento ya está actualizado', 'Usa "Forzar" para reindexar de todos modos.')
      else notify.success('Reindexación iniciada', r.document.filename)
      void qc.invalidateQueries({ queryKey: documentKeys.all })
    },
    onError: (e) => notify.error('No se pudo reindexar', toUserMessage(e)),
  })
}
