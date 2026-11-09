/**
 * Contratos del backend (src/ars/schemas/api.py). Los esquemas zod son la única fuente de verdad:
 * los tipos TypeScript se infieren de ellos, y los servicios validan las respuestas con ellos.
 */
import { z } from 'zod';

const nullableStr = z.string().nullable().optional();
const dict = z.record(z.string(), z.unknown());

// ---- Enumeraciones reales del backend (src/ars/enums.py) -----------------------------------
export const RESEARCH_STATUSES = [
  'pending',
  'running',
  'completed',
  'failed',
  'needs_clarification',
  'interrupted',
] as const;
export type ResearchStatus = (typeof RESEARCH_STATUSES)[number];
export const TERMINAL_RESEARCH_STATUSES: readonly string[] = [
  'completed',
  'failed',
  'needs_clarification',
  'interrupted',
];
export const DOCUMENT_STATUSES = ['processing', 'indexed', 'failed'] as const;
export type DocumentStatus = (typeof DOCUMENT_STATUSES)[number];
export const EVALUATION_MODES = ['retrieval', 'A', 'B', 'C'] as const;
export type EvaluationMode = (typeof EVALUATION_MODES)[number];
export const RETRIEVAL_STRATEGIES = [
  'auto',
  'vector',
  'keyword',
  'hybrid',
] as const;
export type RetrievalStrategy = (typeof RETRIEVAL_STRATEGIES)[number];
export const QUERY_TRANSFORMS = [
  'auto',
  'none',
  'rewrite',
  'multi_query',
  'rag_fusion',
  'hyde',
] as const;
export type QueryTransform = (typeof QUERY_TRANSFORMS)[number];
/** Extensiones admitidas por rag/validation.py (ALLOWED). */
export const ALLOWED_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.txt',
  '.md',
  '.markdown',
  '.html',
  '.htm',
] as const;

// ---- Investigaciones ---------------------------------------------------------------------------
export const researchOutSchema = z.object({
  id: z.string(),
  parent_id: nullableStr,
  query: z.string(),
  status: z.string(),
  current_stage: nullableStr,
  stop_reason: nullableStr,
  clarification_questions: z.array(z.string()).nullable().optional(),
  iterations: z.number(),
  tokens_input: z.number(),
  tokens_output: z.number(),
  cost_usd: z.number(),
  created_at: z.string(),
  finished_at: nullableStr,
});
export type ResearchOut = z.infer<typeof researchOutSchema>;

export const researchListSchema = z.object({
  items: z.array(researchOutSchema),
  total: z.number(),
});
export type ResearchList = z.infer<typeof researchListSchema>;

export const researchStatusOutSchema = z.object({
  id: z.string(),
  status: z.string(),
  current_stage: nullableStr,
  iteration: z.number(),
  tokens_input: z.number(),
  tokens_output: z.number(),
  embedding_tokens: z.number(),
  cost_usd: z.number(),
  clarification_questions: z.array(z.string()).nullable().optional(),
  error: nullableStr,
  started_at: nullableStr,
  finished_at: nullableStr,
});
export type ResearchStatusOut = z.infer<typeof researchStatusOutSchema>;

export interface ResearchOptions {
  max_iterations?: number | null;
  token_budget?: number | null;
  top_k?: number | null;
  retrieval_strategy?: RetrievalStrategy | null;
  query_transform?: QueryTransform | null;
  document_ids?: string[] | null;
  parallel?: boolean;
  reinvestigate?: boolean;
}
export interface ResearchCreate {
  query: string;
  options?: ResearchOptions;
  parent_research_id?: string | null;
}

export const sourceOutSchema = z.object({
  label: z.string(),
  document_id: z.string().nullable(),
  document_name: z.string(),
  page_number: z.number().nullable(),
  snippet: z.string(),
  score: z.number(),
});
export type SourceOut = z.infer<typeof sourceOutSchema>;

export const findingOutSchema = z.object({
  statement: z.string(),
  kind: z.string(),
  aspect: z.string().nullable(),
  support_level: z.string(),
  verification_note: z.string().nullable(),
  sources: z.array(z.string()),
});
export type FindingOut = z.infer<typeof findingOutSchema>;

export const reportOutSchema = z.object({
  research_id: z.string(),
  title: z.string(),
  markdown: z.string(),
  content: dict,
  quality: dict,
  sources: z.array(sourceOutSchema),
  findings: z.array(findingOutSchema),
  created_at: z.string(),
});
export type ReportOut = z.infer<typeof reportOutSchema>;

// ---- Documentos --------------------------------------------------------------------------------
export const documentOutSchema = z.object({
  id: z.string(),
  filename: z.string(),
  file_type: z.string(),
  title: z.string().nullable(),
  author: z.string().nullable(),
  document_date: z.string().nullable(),
  size_bytes: z.number(),
  content_hash: z.string(),
  version: z.number(),
  status: z.string(),
  error: z.string().nullable(),
  num_pages: z.number().nullable(),
  num_chunks: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
  indexed_at: z.string().nullable(),
});
export type DocumentOut = z.infer<typeof documentOutSchema>;
export const documentListSchema = z.object({
  items: z.array(documentOutSchema),
  total: z.number(),
});
export type DocumentList = z.infer<typeof documentListSchema>;
export const documentUploadSchema = z.object({
  document: documentOutSchema,
  action: z.enum(['created', 'updated', 'duplicate']),
});
export type DocumentUploadOut = z.infer<typeof documentUploadSchema>;
export const reindexSchema = z.object({
  document: documentOutSchema,
  action: z.enum(['reindexing', 'up_to_date']),
});
export type ReindexOut = z.infer<typeof reindexSchema>;

// ---- Evaluación --------------------------------------------------------------------------------
export const evalItemSchema = z.object({
  id: z.string().min(1),
  question: z.string().min(1),
  reference_answer: z.string().nullable().optional(),
  relevant_documents: z.array(z.string()).default([]),
  expected_keywords: z.array(z.string()).default([]),
  expected_strategy: z.string().nullable().optional(),
  expected_aspects: z.array(z.string()).default([]),
});
/** Cuerpo de POST /evaluations/datasets (validado en el cliente antes de enviar). */
export const datasetCreateSchema = z.object({
  name: z.string().min(1).max(128),
  description: z.string().nullable().optional(),
  items: z.array(evalItemSchema).min(1),
});
export type DatasetCreate = z.infer<typeof datasetCreateSchema>;

export const datasetOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  items: z.array(dict),
  created_at: z.string(),
});
export type DatasetOut = z.infer<typeof datasetOutSchema>;

export interface EvaluationCreate {
  name: string;
  dataset_id: string;
  mode: EvaluationMode;
  top_k: number;
  retrieval_strategy: RetrievalStrategy;
  rerank?: boolean | null;
  use_ragas: boolean;
  max_iterations?: number | null;
  token_budget?: number | null;
}

export const evaluationOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  dataset_id: z.string(),
  mode: z.string(),
  config: dict,
  status: z.string(),
  summary: dict.nullable(),
  error: z.string().nullable(),
  created_at: z.string(),
  finished_at: z.string().nullable(),
});
export type EvaluationOut = z.infer<typeof evaluationOutSchema>;
export const evaluationResultSchema = z.object({
  item_id: z.string(),
  question: z.string(),
  answer: z.string().nullable(),
  status: z.string(),
  metrics: dict,
  retrieved: z.array(z.string()),
  latency_ms: z.number(),
  tokens_input: z.number(),
  tokens_output: z.number(),
  iterations: z.number(),
  error: z.string().nullable(),
});
export type EvaluationResultOut = z.infer<typeof evaluationResultSchema>;
export const evaluationDetailSchema = evaluationOutSchema.extend({
  results: z.array(evaluationResultSchema).default([]),
});
export type EvaluationDetailOut = z.infer<typeof evaluationDetailSchema>;
export const evaluationListSchema = z.object({
  items: z.array(evaluationOutSchema),
  total: z.number(),
});
export type EvaluationList = z.infer<typeof evaluationListSchema>;
export const comparisonSchema = z.object({
  baseline_id: z.string(),
  experiments: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      mode: z.string(),
      dataset_id: z.string(),
      metrics: z.record(z.string(), z.number()),
    }),
  ),
  deltas: z.record(z.string(), z.record(z.string(), z.number().nullable())),
});
export type ComparisonOut = z.infer<typeof comparisonSchema>;

// ---- Sistema -----------------------------------------------------------------------------------
export const healthSchema = z.object({
  status: z.string(),
  version: z.string(),
  checks: dict,
});
export type HealthOut = z.infer<typeof healthSchema>;
/** GET /configuration devuelve Settings.public_dict(): un diccionario plano sin secretos. */
export const configurationSchema = dict;
export type ConfigurationOut = z.infer<typeof configurationSchema>;
