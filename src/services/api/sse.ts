import { ApiError, errorFromResponse } from './errors';
import { authHeaders, buildUrl } from './client';

export interface SseMessage {
  id?: string;
  event: string;
  data: string;
}


export function createSseParser(onMessage: (m: SseMessage) => void) {
  let buffer = '';
  let id: string | undefined;
  let event = '';
  let data: string[] = [];

  const dispatch = () => {
    if (data.length || event)
      onMessage({ id, event: event || 'message', data: data.join('\n') });
    event = '';
    data = [];
  };
  const processLine = (line: string) => {
    if (line === '') return dispatch();
    if (line.startsWith(':')) return; // comentario / keep-alive
    const idx = line.indexOf(':');
    const field = idx === -1 ? line : line.slice(0, idx);
    let value = idx === -1 ? '' : line.slice(idx + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
    else if (field === 'id' && !value.includes('\0')) id = value;
  };

  return {
    push(chunk: string) {
      buffer += chunk;
      const lines = buffer.split(/\r\n|\n|\r/);
      buffer = lines.pop() ?? '';
      lines.forEach(processLine);
    },
  };
}

export interface ConnectOptions {
  lastEventId?: number;
  signal: AbortSignal;
  onOpen: () => void;
  onMessage: (m: SseMessage) => void;
}

export async function connectSse(
  path: string,
  opts: ConnectOptions,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    'Cache-Control': 'no-cache',
    ...authHeaders(),
  };
  if (opts.lastEventId) headers['Last-Event-ID'] = String(opts.lastEventId);
  let res: Response;
  try {
    res = await fetchImpl(buildUrl(path), { headers, signal: opts.signal });
  } catch (cause) {
    if (opts.signal.aborted)
      throw new ApiError('aborted', 'Conexión cancelada.', undefined, {
        cause,
      });
    throw new ApiError(
      'network',
      'Se perdió la conexión con el backend.',
      undefined,
      { cause },
    );
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* cuerpo no JSON */
    }
    throw errorFromResponse(res.status, body);
  }
  if (!res.body)
    throw new ApiError(
      'network',
      'El navegador no admite lectura en streaming.',
    );
  opts.onOpen();
  const parser = createSseParser(opts.onMessage);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
  } catch (cause) {
    if (opts.signal.aborted)
      throw new ApiError('aborted', 'Conexión cancelada.', undefined, {
        cause,
      });
    throw new ApiError(
      'network',
      'Se interrumpió el stream de eventos.',
      undefined,
      { cause },
    );
  }
}
