import { request } from './api/client'
import {
  documentListSchema, documentOutSchema, documentUploadSchema, reindexSchema,
  type DocumentList, type DocumentOut, type DocumentUploadOut, type ReindexOut,
} from '@/types/api'

export const documentsService = {
  /** POST /documents/upload (multipart, campo `file`). 202 si se procesa; 200 si es duplicado. */
  upload: (file: File, signal?: AbortSignal) => {
    const form = new FormData()
    form.append('file', file)
    // Las subidas grandes pueden tardar más que una petición normal.
    return request<DocumentUploadOut>('/documents/upload', { method: 'POST', formData: form, schema: documentUploadSchema, signal, timeoutMs: 120_000 })
  },
  /** GET /documents?limit&offset&file_type&status */
  list: (params: { limit?: number; offset?: number; file_type?: string; status?: string } = {}, signal?: AbortSignal) =>
    request<DocumentList>('/documents', { query: params, schema: documentListSchema, signal }),
  /** GET /documents/{id} */
  get: (id: string, signal?: AbortSignal) => request<DocumentOut>(`/documents/${id}`, { schema: documentOutSchema, signal }),
  /** DELETE /documents/{id} → 204 */
  remove: (id: string) => request<void>(`/documents/${id}`, { method: 'DELETE', as: 'none' }),
  /** POST /documents/{id}/reindex?force */
  reindex: (id: string, force = false) => request<ReindexOut>(`/documents/${id}/reindex`, { method: 'POST', query: { force }, schema: reindexSchema }),
}
