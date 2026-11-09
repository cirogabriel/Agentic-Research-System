from fakes import FakeLLM, FakeToolbox
from langgraph.checkpoint.memory import InMemorySaver

from ars.graph.builder import build_graph
from ars.graph.nodes import GraphDeps, GraphOptions
from ars.graph.reporter import MemoryReporter
from ars.graph.runner import run_research
from ars.schemas.agents import (
    AnalysisOutput,
    FindingDraft,
    PlannedTask,
    ReportDraft,
    ReportSection,
    ResearchPlan,
    Verdict,
    VerificationVerdicts,
)
from ars.schemas.query import QueryUnderstanding

QUERY = "¿Qué placas tectónicas intervienen en los terremotos de los Andes y por qué ocurren?"
GOOD = FindingDraft(
    statement="La placa de Nazca subduce bajo la placa Sudamericana",
    evidence_labels=["S1"],
)
VALDIVIA = FindingDraft(
    statement="El terremoto de Valdivia de 1960 alcanzó magnitud 9,5",
    evidence_labels=["S2"],
)
BAD = FindingDraft(
    statement="Los terremotos andinos se deben a erupciones solares",
    evidence_labels=["S1"],
)
DRAFT = ReportDraft(
    title="Terremotos andinos",
    executive_summary="La subducción explica la sismicidad [S1].",
    objective="Explicar las causas.",
    sections=[
        ReportSection(
            heading="Causas", body="La placa de Nazca subduce [S1] [S77]."
        )
    ],
    conclusions=["Subducción [S1]"],
    limitations=[],
)
PLAN = ResearchPlan(
    rationale="dos aspectos",
    subtasks=[
        PlannedTask(
            title="Placas", question="¿Qué placas intervienen en los Andes?"
        ),
        PlannedTask(
            title="Causas",
            question="¿Por qué hay subducción de la placa de Nazca?",
        ),
    ],
)


def run(settings, tracker, corpus, responses, **opts):
    llm = FakeLLM(tracker, responses)
    reporter = MemoryReporter()
    options = GraphOptions(**opts)
    final = run_research(
        settings=settings,
        query=QUERY,
        options=options,
        reporter=reporter,
        tracker=tracker,
        thread_id="t",
        llm=llm,
        toolbox=FakeToolbox(corpus),
        checkpointer=InMemorySaver(),
    )
    return final, llm, reporter


def test_happy_path_parallel_workers_and_report(settings, tracker, corpus):
    final, llm, rep = run(
        settings,
        tracker,
        corpus,
        {
            ResearchPlan: PLAN,
            AnalysisOutput: AnalysisOutput(findings=[GOOD]),
            ReportDraft: DRAFT,
        },
    )
    assert (
        final["status"] == "completed"
        and final["stop_reason"] == "sufficient"
        and final["iteration"] == 1
    )
    assert (
        len(final["tasks"]) == 2 and len(final["task_results"]) == 2
    )  # dos workers en paralelo
    assert final["findings"][0]["support"] == "supported"
    md = final["report"]["markdown"]
    assert "## Referencias" in md and "[S77]" not in md and "**[S1]**" in md
    assert (
        final["quality"]["citation_validity"] < 1.0
        and final["quality"]["evidence_coverage"] == 1.0
    )
    agents = {e["agent"] for e in rep.executions}
    assert {
        "query_processor",
        "supervisor",
        "research",
        "analysis",
        "verification",
        "report",
    } <= agents
    assert (
        llm.count("QueryUnderstanding") == 0
        and llm.count("VerificationVerdicts") == 0
    )  # consulta clara y hechos obvios: cero llamadas extra
    types = [e["type"] for e in rep.events]
    assert (
        types[0] == "research.started"
        and "plan.created" in types
        and types[-1] == "research.completed"
    )
    assert final["messages"] and all(m.name for m in final["messages"])


def test_reinvestigation_loop_then_success(settings, tracker, corpus):
    responses = {
        ResearchPlan: PLAN,
        AnalysisOutput: [
            AnalysisOutput(
                findings=[BAD],
                gaps=["¿Qué dice la historia sísmica de Valdivia magnitud?"],
            ),
            AnalysisOutput(findings=[GOOD, VALDIVIA]),
        ],
        VerificationVerdicts: VerificationVerdicts(
            verdicts=[
                Verdict(id="F1", verdict="unsupported", note="no aparece")
            ]
        ),
        ReportDraft: DRAFT,
    }
    final, llm, _ = run(settings, tracker, corpus, responses)
    assert final["iteration"] == 2 and final["status"] == "completed"
    assert (
        any(t["iteration"] == 2 for t in final["tasks"])
        and llm.count("AnalysisOutput") == 2
    )
    assert [f["support"] for f in final["findings"]] == [
        "supported",
        "supported",
    ]


def test_iteration_limit_stops_the_loop(settings, tracker, corpus):
    responses = {
        ResearchPlan: PLAN,
        AnalysisOutput: AnalysisOutput(
            findings=[BAD], gaps=["¿Valdivia magnitud 1960?"]
        ),
        VerificationVerdicts: VerificationVerdicts(
            verdicts=[Verdict(id="F1", verdict="unsupported")]
        ),
        ReportDraft: DRAFT,
    }
    final, llm, _ = run(settings, tracker, corpus, responses, max_iterations=2)
    assert (
        final["iteration"] <= 2
        and final["stop_reason"] in {"max_iterations", "no_new_tasks"}
        and final["status"] == "completed"
    )
    assert "## Limitaciones" in final["report"]["markdown"]


def test_sequential_mode_without_reinvestigation(settings, tracker, corpus):
    responses = {
        ResearchPlan: PLAN,
        AnalysisOutput: AnalysisOutput(findings=[BAD], gaps=["x"]),
        ReportDraft: DRAFT,
    }
    final, llm, _ = run(
        settings,
        tracker,
        corpus,
        responses,
        parallel=False,
        verify_with_llm=False,
        allow_reinvestigation=False,
    )
    assert (
        final["iteration"] == 1
        and final["stop_reason"] == "reinvestigation_disabled"
        and llm.count("VerificationVerdicts") == 0
    )


def test_budget_exhaustion_still_delivers_a_degraded_report(
    settings, tracker, corpus
):
    tracker.token_budget = 150  
    final, _, _ = run(
        settings,
        tracker,
        corpus,
        {
            ResearchPlan: PLAN,
            AnalysisOutput: AnalysisOutput(findings=[GOOD]),
            ReportDraft: DRAFT,
        },
    )
    assert (
        final["status"] == "completed"
        and final.get("budget_exhausted")
        and final["report"]["markdown"]
    )
    assert any(
        "presupuesto" in x.lower() or "sin redacción" in x.lower()
        for x in final["report"]["markdown"].split("\n")
    )


def test_clarification_and_direct_answer_short_circuit(
    settings, tracker, corpus
):
    amb = QueryUnderstanding(
        normalized_query="¿Qué pasó?",
        topic="?",
        objective="?",
        research_type="exploratory",
        is_ambiguous=True,
        clarification_questions=["¿Sobre qué evento?"],
        needs_research=True,
    )
    s2 = settings.model_copy(update={"query_processor_mode": "always"})
    final, _, _ = run(s2, tracker, corpus, {QueryUnderstanding: amb})
    assert (
        final["status"] == "needs_clarification"
        and "report" not in final
        and not final.get("tasks")
    )
    chat = QueryUnderstanding(
        normalized_query="Hola",
        topic="saludo",
        objective="saludar",
        research_type="fact_finding",
        is_ambiguous=False,
        needs_research=False,
        direct_answer="¡Hola!",
    )
    final, llm, _ = run(
        s2,
        tracker.__class__.from_settings(settings),
        corpus,
        {QueryUnderstanding: chat},
    )
    assert (
        final["status"] == "completed"
        and final["report"]["markdown"] == "¡Hola!"
        and final["stop_reason"] == "no_research_needed"
    )


def test_graph_topology_contains_all_agent_nodes(settings, tracker, corpus):
    deps = GraphDeps(
        settings,
        FakeLLM(tracker),
        tracker,
        FakeToolbox(corpus),
        MemoryReporter(),
        GraphOptions(),
    )
    nodes = set(build_graph(deps).get_graph().nodes)
    assert {
        "understand",
        "plan",
        "research_worker",
        "analyze",
        "verify",
        "decide",
        "report",
        "final_evaluation",
    } <= nodes
