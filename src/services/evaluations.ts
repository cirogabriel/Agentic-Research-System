import { request } from './api/client'
import {
  comparisonSchema, datasetOutSchema, evaluationDetailSchema, evaluationListSchema, evaluationOutSchema,
  type ComparisonOut, type DatasetCreate, type DatasetOut, type EvaluationCreate, type EvaluationDetailOut, type EvaluationList, type EvaluationOut,
} from '@/types/api'
import { z } from 'zod'

export const evaluationsService = {
  /** GET /evaluations/datasets */
  datasets: (signal?: AbortSignal) => request<DatasetOut[]>('/evaluations/datasets', { schema: z.array(datasetOutSchema), signal }),
  /** POST /evaluations/datasets → 201 */
  createDataset: (body: DatasetCreate) => request<DatasetOut>('/evaluations/datasets', { method: 'POST', json: body, schema: datasetOutSchema }),
  /** GET /evaluations?limit&offset&dataset_id */
  list: (params: { limit?: number; offset?: number; dataset_id?: string } = {}, signal?: AbortSignal) =>
    request<EvaluationList>('/evaluations', { query: params, schema: evaluationListSchema, signal }),
  /** POST /evaluations → 202. Los modos A/B/C y `use_ragas` consumen tokens del LLM en el backend. */
  create: (body: EvaluationCreate) => request<EvaluationOut>('/evaluations', { method: 'POST', json: body, schema: evaluationOutSchema }),
  /** GET /evaluations/{id} (incluye resultados por ítem) */
  get: (id: string, signal?: AbortSignal) => request<EvaluationDetailOut>(`/evaluations/${id}`, { schema: evaluationDetailSchema, signal }),
  /** GET /evaluations/experiments/compare?experiment_ids&dataset_id (409 si hay menos de 2 completados) */
  compare: (params: { experiment_ids?: string[]; dataset_id?: string }, signal?: AbortSignal) =>
    request<ComparisonOut>('/evaluations/experiments/compare', { query: params, schema: comparisonSchema, signal }),
}
