/** Agrupa las claves de GET /configuration (Settings.public_dict). Cada clave es una variable de entorno del backend en mayúsculas. */
export interface ConfigGroup { title: string; keys: string[] }

export const CONFIG_GROUPS: ConfigGroup[] = [
  { title: 'Modelo generativo', keys: ['llm_model', 'llm_temperature', 'llm_max_output_tokens', 'llm_timeout_seconds', 'llm_max_retries', 'llm_price_input_per_mtok', 'llm_price_output_per_mtok'] },
  { title: 'Modelo de embeddings', keys: ['embedding_model', 'embedding_dimensions', 'embedding_batch_size', 'embedding_price_per_mtok'] },
  { title: 'Estrategia de recuperación', keys: ['retrieval_strategy', 'query_transform', 'retrieval_top_k', 'rrf_k', 'multi_query_count', 'hyde_enabled', 'router_llm_fallback', 'rerank_enabled', 'rerank_model', 'rerank_candidate_multiplier', 'retrieval_cache_ttl_seconds'] },
  { title: 'Investigación y agentes', keys: ['max_iterations', 'max_subtasks', 'max_followup_tasks', 'token_budget', 'report_reserve_ratio', 'evidence_per_task', 'max_findings', 'min_evidence_coverage', 'max_unsupported_ratio', 'verification_mode', 'query_processor_mode', 'agent_tool_transport', 'max_parallel_workers', 'graph_recursion_limit'] },
  { title: 'Ingesta y chunking', keys: ['chunk_strategy', 'chunk_size', 'chunk_overlap', 'max_upload_mb', 'max_pdf_pages'] },
  { title: 'Plataforma', keys: ['app_env', 'log_level', 'background_workers', 'checkpointing_enabled', 'api_key', 'openai_api_key'] },
]
/** Claves que no se muestran: detalles de infraestructura sin valor para el usuario. */
export const HIDDEN_KEYS = new Set(['database_url', 'storage_dir', 'cors_origins', 'db_pool_size', 'log_json', 'mcp_host', 'mcp_port', 'mcp_transport', 'chunk_separators'])

export function formatConfigValue(v: unknown): string {
  if (typeof v === 'boolean') return v ? 'Sí' : 'No'
  if (Array.isArray(v)) return v.join(', ') || '—'
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}
