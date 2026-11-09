import { describe, expect, it } from 'vitest';
import { deriveProgress } from '../progress';
import type { ResearchEvent } from '@/types/events';

let id = 0;
const ev = (
  type: string,
  message = type,
  payload: Record<string, unknown> = {},
): ResearchEvent => ({
  id: ++id,
  type,
  message,
  payload,
  at: '2026-01-01T10:00:00Z',
});
const state = (v: ReturnType<typeof deriveProgress>, k: string) =>
  [...v.stages, ...v.agents].find((x) => x.key === k)!.state;

describe('deriveProgress', () => {
  it('sin eventos todo está pendiente', () => {
    const v = deriveProgress([]);
    expect(v.stages.every((s) => s.state === 'pending')).toBe(true);
    expect(v.agents.every((a) => a.state === 'pending')).toBe(true);
    expect(v.percent).toBe(0);
  });

  it('recorre el flujo completo con eventos reales', () => {
    const events = [
      ev('research.started'),
      ev('query.analyzed'),
      ev('plan.created', '2 subtarea(s) planificada(s)', {
        rationale: 'Dividir en causas y comparación',
        tasks: ['Causas', 'Comparación'],
      }),
      ev('task.started', 'Buscando: Causas', { task: 't1' }),
      ev('task.started', 'Buscando: Comparación', { task: 't2' }),
      ev('task.completed', 'Causas: 3 fragmento(s)', { task: 't1' }),
    ];
    let v = deriveProgress(events);
    expect(state(v, 'planning')).toBe('completed');
    expect(state(v, 'researching')).toBe('running');
    expect(state(v, 'supervisor')).toBe('completed');
    expect(v.plannedTasks).toEqual(['Causas', 'Comparación']);
    expect([v.tasksStarted, v.tasksCompleted]).toEqual([2, 1]);

    // Al terminar todas las subtareas empieza el análisis (inferido, sin evento propio)
    v = deriveProgress([...events, ev('task.completed')]);
    expect(state(v, 'researching')).toBe('completed');
    expect(state(v, 'analyzing')).toBe('running');
    expect(state(v, 'analysis')).toBe('running');

    v = deriveProgress([
      ...events,
      ev('task.completed'),
      ev('analysis.completed', '4 hallazgo(s)'),
    ]);
    expect(state(v, 'analyzing')).toBe('completed');
    expect(state(v, 'verifying')).toBe('running');
    expect(state(v, 'verification')).toBe('running');

    const verified = [
      ...events,
      ev('task.completed'),
      ev('analysis.completed'),
      ev('verification.completed', 'Cobertura 80%'),
    ];
    v = deriveProgress([
      ...verified,
      ev('supervisor.decision', 'Suficiente', {
        action: 'finalize',
        stop_reason: 'sufficient',
      }),
    ]);
    expect(state(v, 'verifying')).toBe('completed');
    expect(state(v, 'reporting')).toBe('running');
    expect(state(v, 'report')).toBe('running');

    v = deriveProgress([
      ...verified,
      ev('supervisor.decision', 'ok', { action: 'finalize' }),
      ev('report.generated', 'Título'),
      ev('research.completed'),
    ]);
    expect(v.terminal).toBe('completed');
    expect(v.percent).toBe(100);
    expect(v.agents.every((a) => a.state === 'completed')).toBe(true);
  });

  it('una decisión "continue" abre una nueva iteración', () => {
    const v = deriveProgress([
      ev('research.started'),
      ev('query.analyzed'),
      ev('plan.created', 'p', { tasks: ['A'] }),
      ev('task.started'),
      ev('task.completed'),
      ev('analysis.completed'),
      ev('verification.completed'),
      ev('supervisor.decision', 'Falta cobertura', { action: 'continue' }),
    ]);
    expect(v.iteration).toBe(2);
    expect(state(v, 'researching')).toBe('running');
    expect(state(v, 'analyzing')).toBe('pending');
    expect(state(v, 'verification')).toBe('pending');
  });

  it('research.failed marca como fallido lo que estaba en ejecución', () => {
    const v = deriveProgress([
      ev('research.started'),
      ev('query.analyzed'),
      ev('plan.created', 'p', { tasks: ['A'] }),
      ev('task.started'),
      ev('research.failed', 'Error en plan: timeout'),
    ]);
    expect(v.terminal).toBe('failed');
    expect(v.errorMessage).toContain('plan');
    expect(v.errorMessage).not.toContain('timeout'); // no se expone el texto de la excepción
    expect(state(v, 'researching')).toBe('failed');
    expect(state(v, 'research')).toBe('failed');
  });

  it('aclaración: expone las preguntas y no avanza etapas', () => {
    const v = deriveProgress([
      ev('research.started'),
      ev('query.analyzed'),
      ev('research.needs_clarification', 'Se requieren aclaraciones', {
        questions: ['¿Qué región?', '¿Qué periodo?'],
      }),
    ]);
    expect(v.terminal).toBe('needs_clarification');
    expect(v.clarificationQuestions).toEqual(['¿Qué región?', '¿Qué periodo?']);
    expect(state(v, 'planning')).toBe('pending');
  });

  it('respuesta directa: completa sin plan', () => {
    const v = deriveProgress([
      ev('research.started'),
      ev('query.analyzed'),
      ev('research.completed', 'Respuesta directa sin investigación'),
    ]);
    expect(v.directAnswer).toBe(true);
    expect(v.percent).toBe(100);
  });

  it('budget.exhausted queda como nota; verificación completa las etapas previas', () => {
    const v = deriveProgress([
      ev('research.started'),
      ev('query.analyzed'),
      ev('plan.created', 'p', { tasks: ['A'] }),
      ev('task.started'),
      ev('task.completed'),
      ev('budget.exhausted', 'Presupuesto agotado'),
      ev('verification.completed'),
    ]);
    expect(v.notes).toContain('Presupuesto agotado');
    expect(state(v, 'analyzing')).toBe('completed');
  });

  it('estado interrumpido sin evento terminal', () => {
    const v = deriveProgress(
      [ev('research.started'), ev('query.analyzed')],
      'interrupted',
    );
    expect(v.terminal).toBe('interrupted');
    expect(v.errorMessage).toMatch(/reanudar/i);
  });
});
