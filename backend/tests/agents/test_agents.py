from fakes import FakeToolbox

from ars.agents.evidence import merge_sources, select_evidence
from ars.agents.report_render import classify, render_markdown, sanitize_citations
from ars.agents.research import ResearchAgent
from ars.agents.supervisor import SupervisorAgent
from ars.agents.verification import VerificationAgent, support_score
from ars.query.processor import QueryProcessor
from ars.schemas.agents import (
    ReportDraft,
    ReportSection,
    ResearchPlan,
    PlannedTask,
    SubTask,
    VerificationVerdicts,
    Verdict,
)
from ars.schemas.query import QueryAnalysis, QueryUnderstanding


def test_query_processor_skips_llm_for_clear_queries(llm, settings):
    qp = QueryProcessor(llm, settings)
    a = qp.process("¿Qué placas tectónicas intervienen en los terremotos de los Andes?")
    assert not a.used_llm and llm.calls == [] and a.language == "es" and a.needs_research


def test_query_processor_uses_llm_for_messy_queries_and_keeps_intent(llm, settings):
    llm.responses[QueryUnderstanding] = QueryUnderstanding(
        normalized_query="Investiga por qué se producen los terremotos en los Andes y qué placas están involucradas", topic="sismología",
        objective="causas de los terremotos", research_type="explanatory", entities=["Andes"], constraints=["Andes"], key_aspects=["tectónica de placas"],
        is_ambiguous=False, needs_research=True)
    a = QueryProcessor(llm, settings).process("investiga por que se producen los terremotos en los andes y que placas estan involucradas")
    assert a.used_llm and a.topic == "sismología" and llm.count("QueryUnderstanding") == 1


def test_query_processor_modes_and_ambiguity(llm, settings):
    never = QueryProcessor(llm, settings.model_copy(update={"query_processor_mode": "never"}))
    assert not never.process("mmm eso").used_llm
    llm.responses[QueryUnderstanding] = QueryUnderstanding(normalized_query="¿Qué pasó?", topic="?", objective="?", research_type="exploratory",
                                                           is_ambiguous=True, clarification_questions=["¿Sobre qué tema?"], needs_research=True)
    a = QueryProcessor(llm, settings).process("que paso con eso")
    assert a.is_ambiguous and a.clarification_questions == ["¿Sobre qué tema?"]
    llm.responses[QueryUnderstanding] = QueryUnderstanding(normalized_query="x", topic="x", objective="x", research_type="exploratory", is_ambiguous=True, needs_research=True)
    assert not QueryProcessor(llm, settings).process("que paso con eso").is_ambiguous  # sin preguntas no se puede aclarar


def analysis(rtype="explanatory", aspects=("a", "b", "c")):
    return QueryAnalysis(normalized_query="¿Por qué hay terremotos en los Andes?", topic="sismología", objective="causas", research_type=rtype, key_aspects=list(aspects),
                         is_ambiguous=False, needs_research=True, language="es")


def test_supervisor_plan_skips_llm_when_simple_and_dedupes(llm, settings):
    sup = SupervisorAgent(llm, settings)
    tasks, _ = sup.plan(analysis("fact_finding", ("magnitud",)))
    assert len(tasks) == 1 and llm.calls == []
    llm.responses[ResearchPlan] = ResearchPlan(rationale="r", subtasks=[PlannedTask(title="A", question="¿Placas?"), PlannedTask(title="B", question="¿placas?"),
                                                                       PlannedTask(title="C", question="¿Subducción?"), PlannedTask(title="D", question="¿Historia?"),
                                                                       PlannedTask(title="E", question="¿Magnitud?")])
    tasks, _ = sup.plan(analysis())
    assert [t.id for t in tasks] == ["t1", "t2", "t3"]  # duplicada eliminada y límite max_subtasks=3


def test_supervisor_decisions(llm, settings, tracker):
    sup = SupervisorAgent(llm, settings, max_iterations=2)
    tasks = [{"id": "t1", "question": "¿Placas?", "transform_hint": "auto"}]
    common = dict(analysis_notes={"gaps": ["¿Qué pasa con los volcanes?"]}, tasks=tasks, tracker=tracker)
    assert sup.decide(iteration=1, verification={"sufficient": True}, **common).stop_reason == "sufficient"
    assert sup.decide(iteration=1, verification={"sufficient": False}, allow_reinvestigation=False, **common).stop_reason == "reinvestigation_disabled"
    assert sup.decide(iteration=2, verification={"sufficient": False}, **common).stop_reason == "max_iterations"
    d = sup.decide(iteration=1, verification={"sufficient": False, "uncovered": [{"id": "t1", "question": "¿Placas?"}]}, **common)
    assert d.action == "continue" and {t.question for t in d.new_tasks} == {"¿Qué pasa con los volcanes?", "¿Placas?"}
    retry = next(t for t in d.new_tasks if t.replaces == "t1")
    assert retry.transform_hint == "rag_fusion" and retry.iteration == 2
    tracker.charge(79_000, 0)  # queda menos del mínimo de trabajo
    assert sup.decide(iteration=1, verification={"sufficient": False}, **common).stop_reason == "budget"


def test_research_agent_falls_back_to_hybrid_when_empty(corpus):
    tb = FakeToolbox(corpus)
    res = ResearchAgent(tb, top_k=3).run(SubTask(id="t1", title="x", question="placa Nazca Sudamericana", strategy_hint="vector"))
    assert res.evidence and res.error is None and res.strategy == "vector"
    empty = ResearchAgent(tb, top_k=3).run(SubTask(id="t2", title="x", question="zzz qqq", strategy_hint="vector"))
    assert not empty.evidence and len(tb.requests) == 3 and tb.requests[-1].strategy == "hybrid"


def test_evidence_selection_labels_and_budget():
    ev = lambda i, t: {"chunk_id": f"c{i}", "document_id": "d", "document_name": "n", "page_number": None, "chunk_index": i, "text": t, "score": 1 - i / 10}
    results = [{"task_id": "t1", "evidence": [ev(1, "x" * 50), ev(2, "y" * 50)]}, {"task_id": "t2", "evidence": [ev(1, "x" * 50), ev(3, "z" * 50)]}]
    update, used = select_evidence(results, {}, per_task=5, max_chars=10_000)
    assert used == ["S1", "S2", "S3"] and update["S1"]["task_ids"] == ["t1", "t2"]  # el mismo fragmento comparte etiqueta
    update2, used2 = select_evidence([{"task_id": "t3", "evidence": [ev(1, "x" * 50), ev(9, "w" * 50)]}], merge_sources({}, update), per_task=5, max_chars=10_000)
    assert used2 == ["S1", "S4"] and merge_sources(update, update2)["S1"]["task_ids"] == ["t1", "t2", "t3"]
    _, used3 = select_evidence(results, {}, per_task=5, max_chars=60)
    assert len(used3) < 3


SOURCES = {"S1": {"label": "S1", "text": "La placa de Nazca subduce bajo la placa Sudamericana.", "task_ids": ["t1"], "document_name": "a.md", "page_number": None, "score": 1.0},
           "S2": {"label": "S2", "text": "El terremoto de Valdivia tuvo magnitud 9,5.", "task_ids": ["t2"], "document_name": "b.md", "page_number": 3, "score": 0.5}}


def finding(i, statement, labels, kind="fact"):
    return {"id": f"F{i}", "statement": statement, "kind": kind, "labels": labels, "aspect": None, "support": None, "note": ""}


def test_support_score():
    assert support_score("Nazca subduce bajo Sudamericana", [SOURCES["S1"]["text"]]) == 1.0
    assert support_score("Los volcanes de Marte", [SOURCES["S1"]["text"]]) == 0.0


def test_verification_is_hybrid_and_never_trusts_missing_support(llm, settings, tracker):
    tasks = [{"id": "t1", "question": "¿Placas?"}, {"id": "t2", "question": "¿Magnitud?"}]
    findings = [finding(1, "La placa de Nazca subduce bajo la placa Sudamericana", ["S1"]),
                finding(2, "El sismo de Valdivia liberó energía enorme y causó un tsunami global", ["S2"]),  # dudoso → LLM
                finding(3, "Hay oro en los Andes", []),  # sin citas
                finding(4, "Dato inventado", ["S99"]),  # cita inexistente
                finding(5, "Probablemente la subducción domina el riesgo", ["S1"], "interpretation")]
    llm.responses[VerificationVerdicts] = VerificationVerdicts(verdicts=[Verdict(id="F2", verdict="unsupported", note="el texto no menciona tsunami")])
    out, summary = VerificationAgent(llm, settings).verify(findings=findings, sources=SOURCES, tasks=tasks, notes={}, tracker=tracker)
    support = {f["id"]: f["support"] for f in out}
    assert support == {"F1": "supported", "F2": "unsupported", "F3": "unsupported", "F4": "unsupported", "F5": "unverified"}
    assert llm.count("VerificationVerdicts") == 1  # una sola llamada por lotes, solo para lo dudoso
    assert summary["coverage"] == 0.5 and not summary["sufficient"] and summary["uncovered"] == [{"id": "t2", "question": "¿Magnitud?"}]


def test_verification_without_llm_degrades_to_lexical(llm, settings, tracker):
    out, summary = VerificationAgent(llm, settings, use_llm=False).verify(
        findings=[finding(1, "El terremoto de Valdivia causó un tsunami enorme en Chile", ["S2"])], sources=SOURCES, tasks=[{"id": "t2", "question": "q"}], notes={}, tracker=tracker)
    assert llm.calls == [] and out[0]["support"] in {"partially_supported", "unsupported"} and not summary["sufficient"]


def test_verification_replaced_task_does_not_block_coverage(llm, settings, tracker):
    tasks = [{"id": "t1", "question": "a"}, {"id": "t2", "question": "b", "replaces": "t1"}]
    sources = {"S1": {**SOURCES["S1"], "task_ids": ["t2"]}}
    _, summary = VerificationAgent(llm, settings, use_llm=False).verify(findings=[finding(1, "La placa de Nazca subduce bajo la placa Sudamericana", ["S1"])],
                                                                         sources=sources, tasks=tasks, notes={}, tracker=tracker)
    assert summary["coverage"] == 1.0 and summary["sufficient"]


def test_report_rendering_removes_invalid_citations_and_separates_facts():
    text, total, invalid = sanitize_citations("A [S1, S9] B [S7] C [S2]", {"S1", "S2"})
    assert (text, total, invalid) == ("A [S1] B  C [S2]", 4, 2)
    findings = [{**finding(1, "Hecho", ["S1"]), "support": "supported"}, {**finding(2, "Idea", ["S1"], "interpretation"), "support": "unverified"},
                {**finding(3, "Dudoso", ["S2"]), "support": "partially_supported", "note": "parcial"}]
    assert {k: len(v) for k, v in classify(findings).items()} == {"facts": 1, "interpretations": 1, "unverified": 1}
    draft = ReportDraft(title="Informe", executive_summary="Resumen [S1] [S42]", objective="Obj", sections=[ReportSection(heading="H", body="Texto [S2]")], conclusions=["C1"], limitations=["L1"])
    md, meta = render_markdown(draft, findings=findings, sources=SOURCES, stats={"iterations": 1, "tasks": 2, "sources": 2, "strategies": ["hybrid"], "supported_facts": 1, "total_facts": 2, "stop_reason": "sufficient"},
                               lang="es", extra_limitations=["L2"])
    for heading in ["## Resumen ejecutivo", "## Metodología utilizada", "### Hechos respaldados", "### Interpretaciones", "### Aspectos no verificados", "### Referencias", "## Conclusiones", "## Limitaciones"]:
        assert heading in md
    assert "[S42]" not in md and "**[S1]** a.md" in md and "pág. 3" in md and meta["citations_invalid"] == 1
