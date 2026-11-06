/** Utilidades puras para presentar el informe (markdown generado por report_render.py). */

export type SectionKind = 'summary' | 'objective' | 'method' | 'findings' | 'comparison' | 'evidence' | 'conclusions' | 'limits' | 'other'

// Encabezados reales del backend (LABELS es/en en agents/report_render.py).
const HEADINGS: Record<Exclude<SectionKind, 'other'>, string[]> = {
  summary: ['resumen ejecutivo', 'executive summary'],
  objective: ['objetivo de la investigación', 'research objective'],
  method: ['metodología utilizada', 'methodology'],
  findings: ['desarrollo de los hallazgos', 'findings'],
  comparison: ['comparaciones', 'comparisons'],
  evidence: ['evidencias y referencias', 'evidence and references'],
  conclusions: ['conclusiones', 'conclusions'],
  limits: ['limitaciones de la investigación', 'limitations'],
}

export function sectionKind(heading: string): SectionKind {
  const h = heading.trim().toLowerCase()
  for (const [kind, names] of Object.entries(HEADINGS)) if (names.includes(h)) return kind as SectionKind
  return 'other'
}

export interface ReportSection { heading: string; body: string; kind: SectionKind }

/** Divide el markdown por encabezados de nivel 2 (ignorando los que están dentro de bloques de código). */
export function splitReportSections(markdown: string): { title: string | null; sections: ReportSection[] } {
  let title: string | null = null
  const sections: ReportSection[] = []
  let current: { heading: string; lines: string[] } | null = null
  let fenced = false
  for (const line of markdown.split('\n')) {
    if (/^\s*```/.test(line)) fenced = !fenced
    if (!fenced) {
      const h1 = /^#\s+(.+)$/.exec(line)
      if (h1 && !title && !current) { title = h1[1]!.trim(); continue }
      const h2 = /^##\s+(.+)$/.exec(line)
      if (h2) {
        if (current) sections.push({ heading: current.heading, body: current.lines.join('\n').trim(), kind: sectionKind(current.heading) })
        current = { heading: h2[1]!.trim(), lines: [] }
        continue
      }
    }
    current?.lines.push(line)
  }
  if (current) sections.push({ heading: current.heading, body: current.lines.join('\n').trim(), kind: sectionKind(current.heading) })
  return { title, sections }
}

const CITE = /\[(S\d+(?:\s*,\s*S\d+)*)\]/g

/** Convierte [S1, S2] en enlaces internos `#src-S1` para poder saltar a la tarjeta de la fuente. No toca bloques de código. */
export function linkifyCitations(markdown: string): string {
  return markdown
    .split(/(```[\s\S]*?```)/g)
    .map((part, i) =>
      i % 2 === 1
        ? part
        : part.replace(CITE, (_m, group: string) =>
            group.split(',').map((l) => l.trim()).map((l) => `[\\[${l}\\]](#src-${l})`).join(' '),
          ),
    )
    .join('')
}

export const num = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined)
export const strList = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [])
