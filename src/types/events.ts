/** Eventos SSE reales emitidos por el backend (graph/nodes.py, services/research.py) y el formato del stream (api/routes/research.py). */
import { z } from 'zod';

export const EVENT_TYPES = {
  started: 'research.started',
  queryAnalyzed: 'query.analyzed',
  needsClarification: 'research.needs_clarification',
  planCreated: 'plan.created',
  taskStarted: 'task.started',
  taskCompleted: 'task.completed',
  analysisCompleted: 'analysis.completed',
  budgetExhausted: 'budget.exhausted',
  verificationCompleted: 'verification.completed',
  supervisorDecision: 'supervisor.decision',
  reportGenerated: 'report.generated',
  completed: 'research.completed',
  failed: 'research.failed',
} as const;

/** Cuerpo `data:` de cada evento: {type, message, payload, at}. El `id:` SSE es el id de fila (entero creciente). */
export const eventDataSchema = z.object({
  type: z.string(),
  message: z.string(),
  payload: z.record(z.string(), z.unknown()).default({}),
  at: z.string(),
});

export interface ResearchEvent {
  id: number;
  type: string;
  message: string;
  payload: Record<string, unknown>;
  at: string;
}
