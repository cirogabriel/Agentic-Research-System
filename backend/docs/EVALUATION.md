# Evaluación automática

Módulo independiente (`ars/evaluation`), expuesto por API (`/evaluations`) y por MCP. Las métricas son **funciones puras** (fáciles de probar); la ejecución de experimentos vive en `evaluation/experiments.py` y `services/evaluation.py`.

## Datasets

Formato JSON (`data/evaluation/sample_retrieval_dataset.json`):

```json
{
  "name": "mi-dataset",
  "description": "...",
  "items": [
    {
      "id": "q1",
      "question": "...",
      "reference_answer": "respuesta de referencia (opcional)",
      "relevant_documents": ["archivo1.md"],
      "expected_keywords": ["palabra"],
      "expected_strategy": "hybrid",
      "expected_aspects": ["aspecto1", "aspecto2"]
    }
  ]
}
```

- `relevant_documents` (nombres de archivo) alimenta las métricas de recuperación (juicio **a nivel de documento**).
- `reference_answer` habilita corrección, _context recall_ y Ragas.
- `expected_keywords` → criterio de completitud; `expected_strategy` → selección de herramientas; `expected_aspects` → delegación.

**Cómo ampliarlo**: añade ítems con preguntas reales de tu dominio y los archivos que _tú_ sabes que contienen la respuesta (idealmente 30–100 ítems, con preguntas simples, comparativas y de varios aspectos). Cárgalo con `POST /evaluations/datasets` o `scripts/seed_sample_data.py` (usa `evaluation.datasets.load_dataset_file`).

## 11.1 Recuperación (`retrieval_metrics.py`)

Sobre el ranking de **documentos únicos**: Recall@K, Precision@K (denominador K), MRR, NDCG@K (relevancia binaria) y latencia (la caché se vacía antes de medir). Modo `retrieval`: no hace llamadas al LLM.

## 11.2 Generación (`generation_metrics.py`, `ragas_runner.py`)

| Métrica            | Determinista (siempre)                                                | Ragas (opcional)           |
| ------------------ | --------------------------------------------------------------------- | -------------------------- |
| Faithfulness       | `faithfulness_lexical`: oraciones cuyos términos están en el contexto | `ragas_faithfulness`       |
| Answer relevancy   | `answer_relevancy_lexical`                                            | `ragas_answer_relevancy`   |
| Answer correctness | `answer_correctness_f1` (F1 de términos vs. referencia)               | `ragas_answer_correctness` |
| Context precision  | `context_precision_doc` (fragmentos de docs relevantes)               | `ragas_context_precision`  |
| Context recall     | `context_recall_lexical`                                              | `ragas_context_recall`     |
| Citation accuracy  | citas válidas / citas totales                                         | —                          |

Las métricas léxicas son aproximaciones **baratas y reproducibles**, no miden comprensión semántica (sinónimos, paráfrasis). Ragas (`use_ragas: true`, requiere `uv sync --extra ragas`) usa un LLM como juez y **consume tokens**; su fallo no invalida las métricas deterministas.

## 11.3 Agentes (`agent_metrics.py`)

Task Completion Rate · Tool Selection Accuracy · Delegation Accuracy · Citation Accuracy · Evidence Coverage · Iterations per Task · Agent Failure Rate · Tokens per task · End-to-end latency (media, p50, p95). Definiciones exactas en el docstring de cada función. Notas: en B/C la cobertura es la de la verificación; en A (sin verificación) se usa el _recall_ de documentos relevantes, por lo que **no es estrictamente comparable**. La precisión de citas de B/C se mide **antes** de depurar etiquetas inexistentes.

## 11.4 Experimentos comparativos

| Modo        | Configuración                                                                           |
| ----------- | --------------------------------------------------------------------------------------- |
| `A`         | RAG convencional: 1 recuperación híbrida + 1 llamada al LLM, sin agentes                |
| `B`         | Supervisor + agentes, **secuencial**, verificación solo léxica, **sin reinvestigación** |
| `C`         | Supervisor + agentes, **paralelo**, verificación con LLM y **ciclo de reinvestigación** |
| `retrieval` | Solo métricas de recuperación                                                           |

Cada experimento guarda resultados por ítem (`evaluation_results`) y un resumen (`evaluation_experiments.summary`) con secciones `retrieval`, `generation`, `agent`, `cost`, `ragas`, `meta`. `GET /evaluations/experiments/compare?dataset_id=…` devuelve, para el último experimento completado de A, B y C, las métricas aplanadas y los **deltas frente a A**, junto con el costo estimado (`cost.cost_usd_total`).

**Cómo interpretar**: la pregunta es si la mejora de calidad (fidelidad, cobertura, citas) justifica el aumento de tokens/latencia de B y C. Con datasets pequeños las diferencias no son estadísticamente concluyentes; usa más ítems y repite.
