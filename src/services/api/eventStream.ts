import { eventDataSchema, type ResearchEvent } from '@/types/events';
import { isApiError } from './errors';
import { connectSse, type ConnectOptions } from './sse';
import type { SseMessage } from './sse';

export type StreamStatus =
  'connecting' | 'live' | 'reconnecting' | 'ended' | 'failed';

export type ConnectFn = (opts: ConnectOptions) => Promise<void>;

export interface RunEventStreamOptions {
  connect: ConnectFn;
  onEvent: (e: ResearchEvent) => void;
  onStatus: (s: StreamStatus) => void;
  onError?: (e: unknown) => void;
  signal: AbortSignal;
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

export type Decoded =
  | { kind: 'event'; event: ResearchEvent }
  | { kind: 'end' }
  | { kind: 'ignore' };

export function decodeMessage(m: SseMessage): Decoded {
  if (m.event === 'end') return { kind: 'end' };
  const id = Number(m.id);
  if (!Number.isInteger(id) || id <= 0) return { kind: 'ignore' };
  try {
    const parsed = eventDataSchema.safeParse(JSON.parse(m.data));
    if (!parsed.success) return { kind: 'ignore' };
    return { kind: 'event', event: { id, ...parsed.data } };
  } catch {
    return { kind: 'ignore' };
  }
}

export const abortableSleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    if (signal.aborted) return resolve();
    const t = setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        resolve();
      },
      { once: true },
    );
  });


function isFatal(e: unknown): boolean {
  return (
    isApiError(e) &&
    e.status !== undefined &&
    e.status >= 400 &&
    e.status < 500 &&
    e.status !== 408 &&
    e.status !== 429
  );
}

export async function runEventStream(o: RunEventStreamOptions): Promise<void> {
  const {
    connect,
    signal,
    maxRetries = 6,
    baseDelayMs = 1000,
    maxDelayMs = 15000,
    sleep = abortableSleep,
  } = o;
  let lastId = 0;
  let ended = false;
  let attempt = 0;

  for (;;) {
    o.onStatus(attempt === 0 ? 'connecting' : 'reconnecting');
    try {
      await connect({
        lastEventId: lastId || undefined,
        signal,
        onOpen: () => o.onStatus('live'),
        onMessage: (m) => {
          const d = decodeMessage(m);
          if (d.kind === 'end') ended = true;
          else if (d.kind === 'event' && d.event.id > lastId) {
            lastId = d.event.id;
            attempt = 0; 
            o.onEvent(d.event);
          }
        },
      });
    } catch (e) {
      if (signal.aborted) return;
      if (isFatal(e)) {
        o.onStatus('failed');
        o.onError?.(e);
        return;
      }
    }
    if (signal.aborted) return;
    if (ended) return o.onStatus('ended');
    attempt += 1;
    if (attempt > maxRetries) {
      o.onStatus('failed');
      o.onError?.(new Error('Se agotaron los reintentos de conexión'));
      return;
    }
    await sleep(Math.min(baseDelayMs * 2 ** (attempt - 1), maxDelayMs), signal);
    if (signal.aborted) return;
  }
}


export const connectResearchEvents =
  (researchId: string): ConnectFn =>
  (opts) =>
    connectSse(`/research/${researchId}/events`, opts);
