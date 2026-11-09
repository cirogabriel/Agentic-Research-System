import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  connectResearchEvents,
  runEventStream,
  type StreamStatus,
} from '@/services/api';
import {
  deriveProgress,
  type ProgressView,
} from '@/features/research/progress';
import { researchKeys } from '@/features/research/queries';
import type { ResearchEvent } from '@/types/events';

export interface ResearchStream {
  events: ResearchEvent[];
  connection: StreamStatus;
  progress: ProgressView;
  /** Reintento manual cuando se agotaron las reconexiones automáticas. */
  reconnect: () => void;
}


export function useResearchStream(
  researchId: string | undefined,
  status?: string,
): ResearchStream {
  const qc = useQueryClient();
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [connection, setConnection] = useState<StreamStatus>('connecting');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!researchId) return;
    setEvents([]);
    const ac = new AbortController();
    const invalidate = () => {
      void qc.invalidateQueries({ queryKey: researchKeys.all });
    };
    void runEventStream({
      connect: connectResearchEvents(researchId),
      signal: ac.signal,
      onStatus: (s) => {
        setConnection(s);
        if (s === 'ended') invalidate();
      },
      onEvent: (e) => {
        setEvents((prev) =>
          prev.some((p) => p.id === e.id) ? prev : [...prev, e],
        );
    
        if (
          e.type === 'research.completed' ||
          e.type === 'research.failed' ||
          e.type === 'research.needs_clarification'
        )
          invalidate();
      },
    });
    return () => ac.abort();
  }, [researchId, attempt, qc]);

  const progress = useMemo(
    () => deriveProgress(events, status),
    [events, status],
  );
  const reconnect = useCallback(() => setAttempt((n) => n + 1), []);
  return { events, connection, progress, reconnect };
}
