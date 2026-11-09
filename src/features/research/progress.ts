import { EVENT_TYPES as E, type ResearchEvent } from '@/types/events';

export type StepState = 'pending' | 'running' | 'completed' | 'failed';
export type StageKey =
  | 'understanding'
  | 'planning'
  | 'researching'
  | 'analyzing'
  | 'verifying'
  | 'reporting';
export type AgentKey =
  'supervisor' | 'research' | 'analysis' | 'verification' | 'report';

export const STAGE_LABELS: Record<StageKey, string> = {
  understanding: 'Comprensión de la consulta',
  planning: 'Planificación',
  researching: 'Investigación',
  analyzing: 'Análisis',
  verifying: 'Verificación',
  reporting: 'Generación del informe',
};
export const AGENT_LABELS: Record<AgentKey, string> = {
  supervisor: 'Supervisor Agent',
  research: 'Research Agent',
  analysis: 'Analysis Agent',
  verification: 'Verification Agent',
  report: 'Report Agent',
};
const STAGE_ORDER: StageKey[] = [
  'understanding',
  'planning',
  'researching',
  'analyzing',
  'verifying',
  'reporting',
];
const AGENT_ORDER: AgentKey[] = [
  'supervisor',
  'research',
  'analysis',
  'verification',
  'report',
];

export interface StageView {
  key: StageKey;
  label: string;
  state: StepState;
}
export interface AgentView {
  key: AgentKey;
  label: string;
  state: StepState;
  detail?: string;
  at?: string;
}
export type Terminal =
  'completed' | 'failed' | 'needs_clarification' | 'interrupted' | null;

export interface ProgressView {
  stages: StageView[];
  agents: AgentView[];
  percent: number;
  iteration: number;
  plannedTasks: string[];
  tasksStarted: number;
  tasksCompleted: number;
  terminal: Terminal;
  errorMessage?: string;
  clarificationQuestions: string[];
  notes: string[];
  directAnswer: boolean;
}

export function safeFailureMessage(raw: string): string {
  const where = /^Error en ([^:]+):/.exec(raw)?.[1]?.trim();
  return where
    ? `La investigación falló durante la etapa «${where}».`
    : 'La investigación falló durante la ejecución.';
}

const str = (v: unknown): string | undefined =>
  typeof v === 'string' ? v : undefined;

export function deriveProgress(
  events: readonly ResearchEvent[],
  status?: string,
): ProgressView {
  const stage = Object.fromEntries(
    STAGE_ORDER.map((k) => [k, 'pending']),
  ) as Record<StageKey, StepState>;
  const agent = Object.fromEntries(
    AGENT_ORDER.map((k) => [
      k,
      {
        state: 'pending' as StepState,
        detail: undefined as string | undefined,
        at: undefined as string | undefined,
      },
    ]),
  ) as Record<AgentKey, { state: StepState; detail?: string; at?: string }>;
  let iteration = 1;
  let planned: string[] = [];
  let started = 0;
  let completed = 0;
  let awaitingTasks = false;
  let terminal: Terminal = null;
  let errorMessage: string | undefined;
  let questions: string[] = [];
  const notes: string[] = [];
  let planSeen = false;

  const setAgent = (
    k: AgentKey,
    state: StepState,
    detail?: string,
    at?: string,
  ) => {
    agent[k] = {
      state,
      detail: detail ?? agent[k].detail,
      at: at ?? agent[k].at,
    };
  };
  
  const completeBefore = (key: StageKey) => {
    for (const k of STAGE_ORDER.slice(0, STAGE_ORDER.indexOf(key)))
      if (stage[k] !== 'failed') stage[k] = 'completed';
  };

  for (const e of events) {
    switch (e.type) {
      case E.started:
        stage.understanding = 'running';
        break;
      case E.queryAnalyzed:
        stage.understanding = 'completed';
        stage.planning = 'running';
        setAgent('supervisor', 'running', 'Planificando subtareas', e.at);
        break;
      case E.needsClarification:
        terminal = 'needs_clarification';
        questions = Array.isArray(e.payload.questions)
          ? (e.payload.questions as unknown[]).filter(
              (q): q is string => typeof q === 'string',
            )
          : [];
        stage.planning = 'pending';
        setAgent('supervisor', 'pending', undefined);
        break;
      case E.planCreated:
        planSeen = true;
        planned = Array.isArray(e.payload.tasks)
          ? (e.payload.tasks as unknown[]).filter(
              (t): t is string => typeof t === 'string',
            )
          : [];
        completeBefore('researching');
        stage.researching = 'running';
        awaitingTasks = true;
        setAgent(
          'supervisor',
          'completed',
          str(e.payload.rationale) ?? e.message,
          e.at,
        );
        setAgent('research', 'running', e.message, e.at);
        break;
      case E.taskStarted:
        awaitingTasks = false;
        started += 1;
        setAgent('research', 'running', e.message, e.at);
        break;
      case E.taskCompleted:
        completed += 1;
        setAgent('research', 'running', e.message, e.at);
        if (e.payload.error)
          notes.push(
            'Una subtarea terminó con error; el sistema continuó con la evidencia disponible.',
          );
        break;
      case E.budgetExhausted:
        notes.push(e.message);
        break;
      case E.analysisCompleted:
        completeBefore('verifying');
        stage.verifying = 'running';
        setAgent('research', 'completed', undefined, e.at);
        setAgent('analysis', 'completed', e.message, e.at);
        setAgent(
          'verification',
          'running',
          'Verificando hallazgos contra las fuentes',
          e.at,
        );
        break;
      case E.verificationCompleted:
        completeBefore('verifying');
        stage.verifying = 'completed';
        setAgent('research', 'completed');
        if (agent.analysis.state !== 'completed')
          setAgent('analysis', 'completed');
        setAgent('verification', 'completed', e.message, e.at);
        setAgent(
          'supervisor',
          'running',
          'Evaluando si la evidencia es suficiente',
          e.at,
        );
        break;
      case E.supervisorDecision:
        setAgent('supervisor', 'completed', e.message, e.at);
        if (e.payload.action === 'continue') {
          iteration += 1;
          started = 0;
          completed = 0;
          awaitingTasks = true;
          stage.researching = 'running';
          stage.analyzing = 'pending';
          stage.verifying = 'pending';
          setAgent('research', 'running', 'Nueva ronda de búsqueda', e.at);
          setAgent('analysis', 'pending');
          setAgent('verification', 'pending');
        } else {
          completeBefore('reporting');
          stage.reporting = 'running';
          setAgent('report', 'running', 'Redactando el informe', e.at);
        }
        break;
      case E.reportGenerated:
        completeBefore('reporting');
        stage.reporting = 'completed';
        setAgent('report', 'completed', e.message, e.at);
        break;
      case E.completed:
        terminal = 'completed';
        for (const k of STAGE_ORDER)
          if (stage[k] === 'running') stage[k] = 'completed';
        for (const k of AGENT_ORDER)
          if (agent[k].state === 'running') agent[k].state = 'completed';
        break;
      case E.failed:
        terminal = 'failed';
        errorMessage = safeFailureMessage(e.message);
        break;
      default:
        break;
    }

    if (
      stage.researching === 'running' &&
      !awaitingTasks &&
      started > 0 &&
      completed >= started
    ) {
      stage.researching = 'completed';
      setAgent('research', 'completed');
      stage.analyzing = 'running';
      setAgent('analysis', 'running', 'Analizando la evidencia recuperada');
    }
    if (e.type === E.analysisCompleted) stage.analyzing = 'completed';
  }

  if (status === 'interrupted' && !terminal) terminal = 'interrupted';
  if (status === 'failed' && !terminal) terminal = 'failed';
  if (terminal === 'failed' || terminal === 'interrupted') {
    for (const k of STAGE_ORDER)
      if (stage[k] === 'running') stage[k] = 'failed';
    for (const k of AGENT_ORDER)
      if (agent[k].state === 'running') agent[k].state = 'failed';
    if (terminal === 'interrupted')
      errorMessage ??=
        'La investigación se interrumpió. Puedes reanudarla desde el último checkpoint.';
  }

  const stages = STAGE_ORDER.map((key) => ({
    key,
    label: STAGE_LABELS[key],
    state: stage[key],
  }));
  const done = stages.filter((s) => s.state === 'completed').length;
  const percent =
    terminal === 'completed' ? 100 : Math.round((done / stages.length) * 100);
  return {
    stages,
    agents: AGENT_ORDER.map((key) => ({
      key,
      label: AGENT_LABELS[key],
      ...agent[key],
    })),
    percent,
    iteration,
    plannedTasks: planned,
    tasksStarted: started,
    tasksCompleted: completed,
    terminal,
    errorMessage,
    clarificationQuestions: questions,
    notes,
    directAnswer: terminal === 'completed' && !planSeen,
  };
}


export function currentStageLabel(view: ProgressView): string | null {
  return view.stages.find((s) => s.state === 'running')?.label ?? null;
}
