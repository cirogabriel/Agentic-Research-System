import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  HelpCircle,
  Loader2,
  RotateCcw,
  Play,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ResearchStream } from '@/hooks/useResearchStream';
import type { ResearchOut } from '@/types/api';
import { buildOptions } from './options';
import { usePreferencesStore } from '@/stores/preferencesStore';
import { useClarify, useCreateResearch, useResume } from './queries';
import { RunningMessage } from './ProgressPanels';
import { ReportMessage, UserMessage } from './ReportViews';

const STOP_REASON: Record<string, string> = {
  error: 'Se produjo un error durante la ejecución.',
  budget: 'Se agotó el presupuesto de tokens.',
  max_iterations: 'Se alcanzó el máximo de iteraciones.',
  analysis_error: 'Falló el análisis de la evidencia.',
};

function AiShell({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone?: 'warn' | 'error';
}) {
  return (
    <div className="message ai-message">
      <div className="message-avatar ai-icon">
        {tone === 'error' ? (
          <AlertTriangle />
        ) : tone === 'warn' ? (
          <HelpCircle />
        ) : (
          <Loader2 />
        )}
      </div>
      <div className="message-body ai-body" style={{ flex: 1, minWidth: 0 }}>
        {children}
      </div>
    </div>
  );
}

function ClarificationMessage({ turn }: { turn: ResearchOut }) {
  const [answer, setAnswer] = useState('');
  const clarify = useClarify(turn.id);
  const questions = turn.clarification_questions ?? [];
  return (
    <AiShell tone="warn">
      <p className="message-meta">
        Sistema de investigación · necesito una aclaración
      </p>
      <p>Para investigar con precisión necesito que aclares lo siguiente:</p>
      <ul style={{ margin: '8px 0 12px', paddingLeft: 18 }}>
        {questions.map((q, i) => (
          <li key={i}>{q}</li>
        ))}
      </ul>
      <div className="field">
        <label htmlFor={`clar-${turn.id}`}>Tu respuesta</label>
        <textarea
          id={`clar-${turn.id}`}
          className="textarea"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          maxLength={4000}
          disabled={clarify.isPending}
        />
      </div>
      <div className="modal-actions" style={{ marginTop: 10 }}>
        <Button
          size="sm"
          disabled={!answer.trim() || clarify.isPending}
          onClick={() => clarify.mutate(answer.trim())}
        >
          {clarify.isPending ? 'Enviando…' : 'Enviar aclaración'}
        </Button>
      </div>
    </AiShell>
  );
}

function FailedMessage({ turn }: { turn: ResearchOut }) {
  const navigate = useNavigate();
  const resume = useResume(turn.id);
  const create = useCreateResearch();
  const defaults = usePreferencesStore((s) => s.defaults);
  const interrupted = turn.status === 'interrupted';
  return (
    <AiShell tone="error">
      <p className="message-meta">
        Sistema de investigación · {interrupted ? 'interrumpida' : 'falló'}
      </p>
      <p>
        {interrupted
          ? 'La investigación se interrumpió (por ejemplo, por un reinicio del servicio).'
          : 'La investigación no pudo completarse.'}
        {turn.stop_reason && STOP_REASON[turn.stop_reason]
          ? ` ${STOP_REASON[turn.stop_reason]}`
          : ''}
      </p>
      <p className="text-sm-muted" style={{ marginTop: 6 }}>
        Puedes reanudarla desde el último checkpoint o lanzarla de nuevo como
        una investigación nueva.
      </p>
      <div className="row-wrap" style={{ marginTop: 12 }}>
        <Button
          size="xs"
          onClick={() => resume.mutate()}
          disabled={resume.isPending}
        >
          <Play /> Reanudar
        </Button>
        <Button
          size="xs"
          variant="outline"
          disabled={create.isPending}
          onClick={() =>
            create.mutate(
              {
                query: turn.query,
                options: buildOptions(defaults, []),
                parent_research_id: turn.parent_id ?? null,
              },
              { onSuccess: (r) => navigate(`/research/${r.id}`) },
            )
          }
        >
          <RotateCcw /> Reintentar como nueva
        </Button>
      </div>
    </AiShell>
  );
}

export function TurnView({
  turn,
  stream,
}: {
  turn: ResearchOut;
  stream?: ResearchStream;
}) {
  let ai;
  switch (turn.status) {
    case 'completed':
      ai = <ReportMessage turn={turn} />;
      break;
    case 'needs_clarification':
      ai = <ClarificationMessage turn={turn} />;
      break;
    case 'failed':
    case 'interrupted':
      ai = <FailedMessage turn={turn} />;
      break;
    default:
      ai = stream ? (
        <RunningMessage stream={stream} />
      ) : (
        <AiShell>
          <p className="text-sm-muted">En cola…</p>
        </AiShell>
      );
  }
  return (
    <>
      <UserMessage turn={turn} />
      {ai}
    </>
  );
}
