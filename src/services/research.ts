import { request } from './api/client';
import {
  reportOutSchema,
  researchListSchema,
  researchOutSchema,
  researchStatusOutSchema,
  type ResearchCreate,
  type ResearchList,
  type ResearchOut,
  type ResearchStatusOut,
  type ReportOut,
} from '@/types/api';

export const researchService = {
  /** POST /research */
  create: (body: ResearchCreate, signal?: AbortSignal) =>
    request<ResearchOut>('/research', {
      method: 'POST',
      json: body,
      schema: researchOutSchema,
      signal,
    }),
  /** GET /research?limit&offset&status */
  list: (
    params: { limit?: number; offset?: number; status?: string } = {},
    signal?: AbortSignal,
  ) =>
    request<ResearchList>('/research', {
      query: params,
      schema: researchListSchema,
      signal,
    }),
  /** GET /research/{id} */
  get: (id: string, signal?: AbortSignal) =>
    request<ResearchOut>(`/research/${id}`, {
      schema: researchOutSchema,
      signal,
    }),
  /** GET /research/{id}/status */
  status: (id: string, signal?: AbortSignal) =>
    request<ResearchStatusOut>(`/research/${id}/status`, {
      schema: researchStatusOutSchema,
      signal,
    }),
  /** GET /research/{id}/report?format=json */
  report: (id: string, signal?: AbortSignal) =>
    request<ReportOut>(`/research/${id}/report`, {
      query: { format: 'json' },
      schema: reportOutSchema,
      signal,
    }),
  /** POST /research/{id}/clarifications */
  clarify: (id: string, answer: string) =>
    request<ResearchOut>(`/research/${id}/clarifications`, {
      method: 'POST',
      json: { answer },
      schema: researchOutSchema,
    }),
  /** POST /research/{id}/resume */
  resume: (id: string) =>
    request<ResearchOut>(`/research/${id}/resume`, {
      method: 'POST',
      schema: researchOutSchema,
    }),
};

/** GET /research/{id}/report?format=markdown  */
export const fetchReportMarkdown = (id: string) =>
  request<string>(`/research/${id}/report`, {
    query: { format: 'markdown' },
    as: 'text',
  });
