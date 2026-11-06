"""Query Understanding: normaliza la consulta con un LLM solo cuando hace falta (estrategia económica)."""
from __future__ import annotations

import re
from collections import Counter

from ars.config import Settings
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord
from ars.schemas.query import QueryAnalysis, QueryUnderstanding, ResearchType
from ars.utils.text import content_tokens, detect_language, normalize_whitespace

_COMPARE = re.compile(r"\b(compar\w*|versus|vs\.?|diferenci\w*|differences?|contrast\w*)\b", re.I)
_EXPLAIN = re.compile(r"\b(por qu[eé]|porque|causas?|why|how|c[oó]mo|explica\w*|explain)\b", re.I)
_DEFINE = re.compile(r"\b(qu[eé] es|qu[eé] son|what is|what are|define|defin\w*)\b", re.I)
_VAGUE_START = re.compile(r"^(eso|esto|aquello|it|that|this|and|y|pero|but)\b", re.I)

SYSTEM = """You are the Query Understanding component of a research system.
Analyse the user's request and return a structured representation.
Rules:
- normalized_query: fix spelling/grammar/accents ONLY. Keep the user's language, intent and scope. NEVER add assumptions, places, dates or entities that the user did not state.
- constraints: only regions, periods, sources or conditions explicitly mentioned.
- is_ambiguous=true ONLY if research cannot reasonably start without an important assumption; then give up to 3 short clarification_questions.
- Overly general questions are NOT ambiguous: broaden into key_aspects instead.
- needs_research=false only for greetings/small talk/requests that need no documents; then give a brief direct_answer.
- If previous research context is provided, resolve references ('it', 'that') against it, but do not import its conclusions."""


class QueryProcessor:
    def __init__(self, llm: StructuredLLM, settings: Settings) -> None:
        self.llm, self.settings = llm, settings

    @staticmethod
    def looks_clear(query: str) -> bool:
        """Reglas baratas: consulta bien formada → no hace falta gastar una llamada al LLM."""
        q = query.strip()
        words = q.split()
        if not 6 <= len(words) <= 120 or len(q) > 1200:
            return False
        if not (q[0].isupper() or q[0] in "¿¡"):  # sin mayúscula inicial suele indicar texto sin revisar
            return False
        if not re.search(r"[?.!]$", q):
            return False
        if _VAGUE_START.match(q) or re.search(r"(.)\1{3,}", q):
            return False
        return True

    @staticmethod
    def heuristic(query: str) -> QueryAnalysis:
        q = normalize_whitespace(query)
        counts = Counter(content_tokens(q))
        aspects = [w for w, _ in counts.most_common(5)]
        rtype: ResearchType = "exploratory"
        if _COMPARE.search(q):
            rtype = "comparative"
        elif _EXPLAIN.search(q):
            rtype = "explanatory"
        elif _DEFINE.search(q):
            rtype = "descriptive"
        # Entidades: palabras capitalizadas que no inician la oración, más cifras de 3-4 dígitos.
        entities = list(dict.fromkeys(re.findall(r"(?<![.¿?¡!]\s)(?<!^)\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+\b|\b\d{3,4}\b", q)))
        return QueryAnalysis(
            normalized_query=q, topic=" ".join(aspects[:3]) or q[:60], objective=q, research_type=rtype, entities=entities[:8],
            constraints=[], key_aspects=aspects, is_ambiguous=False, clarification_questions=[], needs_research=True,
            language=detect_language(q), used_llm=False,
        )

    def process(self, query: str, *, parent_context: str = "", rec: ExecutionRecord | None = None) -> QueryAnalysis:
        mode = self.settings.query_processor_mode
        use_llm = mode == "always" or (mode == "auto" and (bool(parent_context) or not self.looks_clear(query)))
        if not use_llm:
            return self.heuristic(query)
        user = f"<previous_research>\n{parent_context}\n</previous_research>\n\n" if parent_context else ""
        out = self.llm.structured(QueryUnderstanding, system=SYSTEM, user=f"{user}User request:\n{query}", rec=rec, max_tokens=500)
        analysis = QueryAnalysis(**out.model_dump(), language=detect_language(query), used_llm=True)
        analysis.normalized_query = normalize_whitespace(analysis.normalized_query) or normalize_whitespace(query)
        analysis.clarification_questions = analysis.clarification_questions[:3]
        if analysis.is_ambiguous and not analysis.clarification_questions:
            analysis.is_ambiguous = False  # sin preguntas concretas no podemos pedir aclaración
        return analysis
