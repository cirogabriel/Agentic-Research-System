import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Check,
  Copy,
  Download,
  FileText,
  Lightbulb,
  ListChecks,
  Scale,
  Search,
  Sparkles,
  Target,
  FlaskConical,
  UserRound,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LoadingState, ErrorState } from '@/components/common/States';
import { MarkdownView } from '@/components/common/MarkdownView';
import { fetchReportMarkdown } from '@/services/research';
import { toUserMessage } from '@/services/api';
import { notify } from '@/stores/toastStore';
import type { FindingOut, ReportOut, ResearchOut } from '@/types/api';
import { formatPercent, formatTime, type Tone } from '@/utils/format';
import { useReport } from './queries';
import {
  linkifyCitations,
  num,
  splitReportSections,
  strList,
  type SectionKind,
} from './reportUtils';
import { SourceCard } from './SourceCard';

const SUPPORT: Record<string, { label: string; tone: Tone }> = {
  supported: { label: 'Respaldado', tone: 'complete' },
  partially_supported: { label: 'Parcial', tone: 'warn' },
  unsupported: { label: 'Sin respaldo', tone: 'error' },
  contradicted: { label: 'Contradicho', tone: 'error' },
  unverified: { label: 'No verificado', tone: 'idle' },
};
export function SupportBadge({ level }: { level: string }) {
  const m = SUPPORT[level] ?? { label: level, tone: 'idle' as Tone };
  return <span className={`badge ${m.tone}`}>{m.label}</span>;
}

const SECTION_ICON: Record<SectionKind, typeof FileText> = {
  summary: FileText,
  objective: Target,
  method: FlaskConical,
  findings: Search,
  comparison: Scale,
  evidence: BookOpen,
  conclusions: Lightbulb,
  limits: AlertTriangle,
  other: FileText,
};

function QualityChips({ quality }: { quality: Record<string, unknown> }) {
  const coverage = num(quality.evidence_coverage);
  const citations = num(quality.citation_validity);
  const supported = num(quality.supported_fact_ratio);
  return (
    <div className="row-wrap" style={{ gap: 6 }}>
      {coverage !== undefined && (
        <span className="badge plain">
          Cobertura de evidencia {formatPercent(coverage, 0)}
        </span>
      )}
      {citations !== undefined && (
        <span className="badge plain">
          Citas válidas {formatPercent(citations, 0)}
        </span>
      )}
      {supported !== undefined && (
        <span className="badge plain">
          Hechos respaldados {formatPercent(supported, 0)}
        </span>
      )}
      {quality.degraded_report === true && (
        <span className="badge warn">
          Informe degradado (sin redacción LLM)
        </span>
      )}
    </div>
  );
}

function FindingsTable({ findings }: { findings: FindingOut[] }) {
  if (!findings.length)
    return (
      <p className="text-sm-muted">
        El backend no registró hallazgos para esta investigación.
      </p>
    );
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Hallazgo</th>
            <th>Tipo</th>
            <th>Verificación</th>
            <th>Fuentes</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f, i) => (
            <tr key={i}>
              <td style={{ minWidth: 260 }}>
                {f.aspect && <div className="hint">{f.aspect}</div>}
                {f.statement}
                {f.verification_note && (
                  <div className="hint">{f.verification_note}</div>
                )}
              </td>
              <td>
                {f.kind === 'interpretation' ? 'Interpretación' : 'Hecho'}
              </td>
              <td>
                <SupportBadge level={f.support_level} />
              </td>
              <td className="mono">{f.sources.join(', ') || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


export function ReportDocument({ report }: { report: ReportOut }) {
  const [target, setTarget] = useState<string | null>(null);
  const { sections } = useMemo(
    () => splitReportSections(report.markdown),
    [report.markdown],
  );
  useEffect(() => {
    if (target)
      document
        .getElementById(`doc-${report.research_id}-${target}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [target, report.research_id]);
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>{report.title}</h2>
      <QualityChips quality={report.quality} />
      {sections.map((s) => {
        const Icon = SECTION_ICON[s.kind];
        return (
          <section key={s.heading} className="report-section">
            <h3>
              <Icon />
              {s.heading}
            </h3>
            <MarkdownView
              markdown={linkifyCitations(s.body)}
              onCite={setTarget}
            />
          </section>
        );
      })}
      <section className="report-section">
        <h3>
          <ListChecks />
          Hallazgos verificados
        </h3>
        <FindingsTable findings={report.findings} />
      </section>
      <section className="report-section">
        <h3>
          <BookOpen />
          Fuentes ({report.sources.length})
        </h3>
        <div className="flex flex-col gap-2">
          {report.sources.length === 0 && (
            <p className="text-sm-muted">Sin fuentes registradas.</p>
          )}
          {report.sources.map((s) => (
            <SourceCard
              key={s.label}
              source={s}
              anchorId={`doc-${report.research_id}-${s.label}`}
              highlighted={target === s.label}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function ReportActions({ report }: { report: ReportOut }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report.markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      notify.error(
        'No se pudo copiar',
        'El navegador no permitió acceder al portapapeles.',
      );
    }
  };
  const download = async () => {
    try {
      const md = await fetchReportMarkdown(report.research_id);
      const url = URL.createObjectURL(
        new Blob([md], { type: 'text/markdown;charset=utf-8' }),
      );
      const a = Object.assign(document.createElement('a'), {
        href: url,
        download: `informe-${report.research_id.slice(0, 8)}.md`,
      });
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      notify.error('No se pudo descargar el informe', toUserMessage(e));
    }
  };
  return (
    <>
      <Button variant="outline" size="xs" onClick={copy}>
        {copied ? <Check /> : <Copy />}
        {copied ? 'Copiado' : 'Copiar Markdown'}
      </Button>
      <Button variant="outline" size="xs" onClick={download}>
        <Download /> Descargar .md
      </Button>
    </>
  );
}


export function ReportMessage({ turn }: { turn: ResearchOut }) {
  const { data: report, isLoading, error, refetch } = useReport(turn.id, true);
  const [full, setFull] = useState(false);
  const [allSources, setAllSources] = useState(false);
  const time = formatTime(turn.finished_at ?? turn.created_at);

  let body;
  if (isLoading) body = <LoadingState label="Cargando informe" rows={3} />;
  else if (error || !report)
    body = (
      <ErrorState
        error={error}
        onRetry={() => void refetch()}
        title="No se pudo cargar el informe"
      />
    );
  else {
    const summary =
      typeof report.content.executive_summary === 'string'
        ? report.content.executive_summary
        : null;
    const conclusions = strList(report.content.conclusions);
    const findings = [...report.findings]
      .sort(
        (a, b) =>
          Number(b.support_level === 'supported') -
          Number(a.support_level === 'supported'),
      )
      .slice(0, 3);
    const shown = allSources ? report.sources : report.sources.slice(0, 3);
    body = (
      <>
        <h2>{report.title}</h2>
        {summary ? (
          <MarkdownView markdown={summary} />
        ) : (
          <p className="text-sm-muted">
            Este informe no incluye resumen ejecutivo.
          </p>
        )}
        {findings.length > 0 && (
          <div className="finding-grid">
            {findings.map((f, i) => (
              <div key={i}>
                <p className="finding-number">
                  {String(i + 1).padStart(2, '0')}
                </p>
                <p className="finding-title">
                  {f.aspect ?? `Hallazgo ${i + 1}`}
                </p>
                <p className="finding-copy">{f.statement}</p>
                <div style={{ marginTop: 8 }}>
                  <SupportBadge level={f.support_level} />
                </div>
              </div>
            ))}
          </div>
        )}
        {conclusions.length > 0 && (
          <div className="conclusion-box">
            <div className="conclusion-icon">
              <Lightbulb />
            </div>
            <div>
              <p className="text-xs font-semibold">
                Conclusión de la investigación
              </p>
              <ul
                className="mt-1 text-xs leading-5 text-muted-foreground"
                style={{ paddingLeft: 16, margin: '4px 0 0' }}
              >
                {conclusions.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        <div className="sources-section">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold">
              Fuentes utilizadas{' '}
              <span className="ml-1 text-muted-foreground">
                ({report.sources.length})
              </span>
            </p>
            {report.sources.length > 3 && (
              <button
                className="link-accent"
                onClick={() => setAllSources((v) => !v)}
              >
                {allSources ? 'Ver menos' : 'Ver todas las fuentes'}
              </button>
            )}
          </div>
          <div className="flex flex-col gap-2">
            {report.sources.length === 0 && (
              <p className="text-sm-muted">Sin fuentes registradas.</p>
            )}
            {shown.map((s) => (
              <SourceCard
                key={s.label}
                source={s}
                anchorId={`sum-${report.research_id}-${s.label}`}
              />
            ))}
          </div>
        </div>
        <div className="row-wrap" style={{ marginTop: 16 }}>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => setFull((v) => !v)}
            aria-expanded={full}
          >
            <FileText />{' '}
            {full ? 'Ocultar informe completo' : 'Ver informe completo'}
          </Button>
          <ReportActions report={report} />
        </div>
        {full && (
          <div
            style={{
              marginTop: 16,
              paddingTop: 8,
              borderTop: '1px solid #ecebf0',
            }}
          >
            <ReportDocument report={report} />
          </div>
        )}
      </>
    );
  }
  return (
    <div className="message ai-message">
      <div className="message-avatar ai-icon">
        <Sparkles />
      </div>
      <div className="message-body ai-body" style={{ minWidth: 0, flex: 1 }}>
        <div className="message-meta flex items-center gap-2">
          <span>Sistema de investigación · {time}</span>
          {report && num(report.quality.evidence_coverage) !== undefined && (
            <span className="verified-badge">
              ✓ Verificada · cobertura{' '}
              {formatPercent(num(report.quality.evidence_coverage)!, 0)}
            </span>
          )}
        </div>
        {body}
      </div>
    </div>
  );
}

export function UserMessage({ turn }: { turn: ResearchOut }) {
  return (
    <div className="message user-message">
      <div className="message-body">
        <p className="message-meta">Tú · {formatTime(turn.created_at)}</p>
        <p style={{ whiteSpace: 'pre-wrap' }}>{turn.query}</p>
      </div>
      <div className="message-avatar user-icon">
        <UserRound />
      </div>
    </div>
  );
}
