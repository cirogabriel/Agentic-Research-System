"""Evaluación opcional con Ragas (LLM-as-judge). Requiere el extra 'ragas' y consume tokens de OpenAI.

Nota de compatibilidad: la API de Ragas cambia entre versiones menores; este módulo asume la forma
`evaluate(EvaluationDataset, metrics=[...], llm=..., embeddings=...)` de la serie 0.3.x y está aislado aquí
para que un ajuste futuro no afecte al resto del sistema.
"""
from __future__ import annotations

from typing import Any

from ars.config import Settings
from ars.exceptions import ConfigurationError

_INPUT_COLUMNS = {"user_input", "response", "retrieved_contexts", "reference"}


def run_ragas(samples: list[dict[str, Any]], settings: Settings) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """samples: [{question, answer, contexts, reference}] → (medias por métrica, puntuaciones por muestra)."""
    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas import EvaluationDataset, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import answer_correctness, answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError as exc:
        raise ConfigurationError("Ragas no está instalado. Usa: uv sync --extra ragas") from exc
    usable = [s for s in samples if s.get("reference") and s.get("answer")]
    if not usable:
        raise ConfigurationError("Ragas necesita 'reference_answer' en los ítems del dataset")
    key = settings.openai_api_key.get_secret_value() or None
    llm = LangchainLLMWrapper(ChatOpenAI(model=settings.llm_model, api_key=key, temperature=0, base_url=settings.openai_base_url or None))
    emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=settings.embedding_model, api_key=key, base_url=settings.openai_base_url or None))
    dataset = EvaluationDataset.from_list([{"user_input": s["question"], "response": s["answer"], "retrieved_contexts": s["contexts"], "reference": s["reference"]} for s in usable])
    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, answer_correctness, context_precision, context_recall], llm=llm, embeddings=emb, show_progress=False)
    df = result.to_pandas()
    cols = [c for c in df.columns if c not in _INPUT_COLUMNS and str(df[c].dtype).startswith(("float", "int"))]
    means = {f"ragas_{c}": round(float(df[c].mean()), 4) for c in cols}
    per_item = [{f"ragas_{c}": (None if row[c] != row[c] else round(float(row[c]), 4)) for c in cols} for _, row in df.iterrows()]
    return means, per_item
