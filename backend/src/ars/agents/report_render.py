from __future__ import annotations

import re
from typing import Any

from ars.enums import Support
from ars.schemas.agents import ReportDraft

LABELS = {
    "es": {
        "summary": "Resumen ejecutivo",
        "objective": "Objetivo de la investigación",
        "method": "Metodología utilizada",
        "findings": "Desarrollo de los hallazgos",
        "comparison": "Comparaciones",
        "evidence": "Evidencias y referencias",
        "facts": "Hechos respaldados por las fuentes",
        "interp": "Interpretaciones",
        "unverified": "Aspectos no verificados o parcialmente respaldados",
        "refs": "Referencias",
        "conclusions": "Conclusiones",
        "limits": "Limitaciones de la investigación",
        "none": "Ninguno.",
        "page": "pág.",
    },
    "en": {
        "summary": "Executive summary",
        "objective": "Research objective",
        "method": "Methodology",
        "findings": "Findings",
        "comparison": "Comparisons",
        "evidence": "Evidence and references",
        "facts": "Facts supported by sources",
        "interp": "Interpretations",
        "unverified": "Unverified or partially supported items",
        "refs": "References",
        "conclusions": "Conclusions",
        "limits": "Limitations",
        "none": "None.",
        "page": "p.",
    },
}
_CITE = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")


def sanitize_citations(text: str, valid: set[str]) -> tuple[str, int, int]:
    """Elimina etiquetas de cita inexistentes. Devuelve (texto, citas_totales, citas_inválidas)."""
    total = invalid = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal total, invalid
        labels = [x.strip() for x in m.group(1).split(",")]
        total += len(labels)
        ok = [lb for lb in labels if lb in valid]
        invalid += len(labels) - len(ok)
        return f"[{', '.join(ok)}]" if ok else ""

    return _CITE.sub(repl, text), total, invalid


def _cite(labels: list[str]) -> str:
    return f" [{', '.join(labels)}]" if labels else ""


def classify(findings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {
        "facts": [],
        "interpretations": [],
        "unverified": [],
    }
    for f in findings:
        if f.get("kind") == "interpretation":
            out["interpretations"].append(f)
        elif f.get("support") == Support.SUPPORTED.value:
            out["facts"].append(f)
        else:
            out["unverified"].append(f)
    return out


def methodology(stats: dict[str, Any], lang: str) -> str:
    if lang == "es":
        return (
            f"Se realizaron {stats['iterations']} iteración(es) con {stats['tasks']} subtarea(s) de búsqueda sobre la colección documental "
            f"(estrategias: {', '.join(stats['strategies']) or 'n/d'}). Se recuperaron {stats['sources']} fragmentos únicos; "
            f"{stats['supported_facts']} de {stats['total_facts']} afirmaciones fácticas quedaron respaldadas tras la verificación. "
            f"Motivo de finalización: {stats['stop_reason']}."
        )
    return (
        f"{stats['iterations']} iteration(s) with {stats['tasks']} search sub-task(s) over the document collection "
        f"(strategies: {', '.join(stats['strategies']) or 'n/a'}). {stats['sources']} unique passages retrieved; "
        f"{stats['supported_facts']} of {stats['total_facts']} factual claims were supported after verification. Stop reason: {stats['stop_reason']}."
    )


def render_markdown(
    draft: ReportDraft,
    *,
    findings: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    stats: dict[str, Any],
    lang: str,
    extra_limitations: list[str],
) -> tuple[str, dict[str, Any]]:
    L = LABELS.get(lang, LABELS["en"])
    valid = set(sources)
    md: list[str] = [
        f"# {draft.title}",
        "",
        f"## {L['summary']}",
        draft.executive_summary,
        "",
        f"## {L['objective']}",
        draft.objective,
        "",
        f"## {L['method']}",
        methodology(stats, lang),
        "",
        f"## {L['findings']}",
    ]
    for sec in draft.sections:
        md += [f"### {sec.heading}", sec.body, ""]
    if draft.comparison:
        md += [f"## {L['comparison']}", draft.comparison, ""]
    cls = classify(findings)
    md += [f"## {L['evidence']}", f"### {L['facts']}"]
    md += [f"- {f['statement']}{_cite(f['labels'])}" for f in cls["facts"]] or [
        L["none"]
    ]
    md += ["", f"### {L['interp']}"]
    md += [
        f"- {f['statement']}{_cite(f['labels'])}"
        for f in cls["interpretations"]
    ] or [L["none"]]
    md += ["", f"### {L['unverified']}"]
    md += [
        f"- {f['statement']}{_cite(f['labels'])} — _{f.get('support')}_: {f.get('note', '')}"
        for f in cls["unverified"]
    ] or [L["none"]]
    in_text = {
        lb.strip()
        for grp in _CITE.findall(" ".join(sec.body for sec in draft.sections))
        for lb in grp.split(",")
    }
    cited = sorted(
        ({lb for f in findings for lb in f.get("labels", [])} | in_text)
        & valid,
        key=lambda x: int(x[1:]),
    )
    md += ["", f"### {L['refs']}"]
    for lb in cited:
        s = sources[lb]
        page = (
            f", {L['page']} {s['page_number']}" if s.get("page_number") else ""
        )
        snippet = re.sub(r"\s+", " ", s["text"])[:160]
        md.append(f"- **[{lb}]** {s['document_name']}{page} — “{snippet}…”")
    md += ["", f"## {L['conclusions']}"] + [f"- {c}" for c in draft.conclusions]
    limits = list(dict.fromkeys(draft.limitations + extra_limitations))
    md += ["", f"## {L['limits']}"] + (
        [f"- {x}" for x in limits] or [L["none"]]
    )
    text = "\n".join(md)
    text, total, invalid = sanitize_citations(text, valid)
    return text, {
        "citations_total": total,
        "citations_invalid": invalid,
        "references": cited,
    }


def render_fallback(
    *,
    query: str,
    findings: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    notes: dict[str, Any],
    stats: dict[str, Any],
    lang: str,
    reason: str,
) -> ReportDraft:

    es = lang == "es"
    facts = [
        f
        for f in findings
        if f.get("support") == Support.SUPPORTED.value
        and f.get("kind") != "interpretation"
    ]
    body = "\n".join(
        f"- {f['statement']}{_cite(f['labels'])}" for f in facts
    ) or (
        "No se pudo respaldar ninguna afirmación."
        if es
        else "No claim could be supported."
    )
    from ars.schemas.agents import ReportSection

    return ReportDraft(
        title=(
            f"Informe preliminar: {query[:90]}"
            if es
            else f"Preliminary report: {query[:90]}"
        ),
        executive_summary=(
            "Informe generado sin redacción por LLM; se listan los hallazgos verificados."
            if es
            else "Report generated without LLM drafting; verified findings are listed."
        ),
        objective=query,
        sections=[
            ReportSection(
                heading="Hallazgos verificados" if es else "Verified findings",
                body=body,
            )
        ],
        comparison=None,
        conclusions=[c for c in notes.get("preliminary_conclusions", [])][:3]
        or [body.split("\n")[0]],
        limitations=[reason],
    )
