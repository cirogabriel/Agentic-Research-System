import { request } from './api/client';
import {
  documentListSchema,
  documentOutSchema,
  documentUploadSchema,
  reindexSchema,
  type DocumentList,
  type DocumentOut,
  type DocumentUploadOut,
  type ReindexOut,
} from '@/types/api';

export const documentsService = {
  upload: (file: File, signal?: AbortSignal) => {
    const form = new FormData();
    form.append('file', file);
    return request<DocumentUploadOut>('/documents/upload', {
      method: 'POST',
      formData: form,
      schema: documentUploadSchema,
      signal,
      timeoutMs: 120_000,
    });
  },
  list: (
    params: {
      limit?: number;
      offset?: number;
      file_type?: string;
      status?: string;
    } = {},
    signal?: AbortSignal,
  ) =>
    request<DocumentList>('/documents', {
      query: params,
      schema: documentListSchema,
      signal,
    }),

  get: (id: string, signal?: AbortSignal) =>
    request<DocumentOut>(`/documents/${id}`, {
      schema: documentOutSchema,
      signal,
    }),

  remove: (id: string) =>
    request<void>(`/documents/${id}`, { method: 'DELETE', as: 'none' }),
  /** POST /documents/{id}/reindex?force */
  reindex: (id: string, force = false) =>
    request<ReindexOut>(`/documents/${id}/reindex`, {
      method: 'POST',
      query: { force },
      schema: reindexSchema,
    }),
};
