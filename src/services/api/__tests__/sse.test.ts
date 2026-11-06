import { describe, expect, it } from 'vitest'
import { createSseParser, connectSse, type SseMessage } from '../sse'

function parse(chunks: string[]): SseMessage[] {
  const out: SseMessage[] = []
  const p = createSseParser((m) => out.push(m))
  chunks.forEach((c) => p.push(c))
  return out
}

describe('createSseParser', () => {
  it('parsea un mensaje con id, event y data', () => {
    const [m] = parse(['id: 7\nevent: plan.created\ndata: {"a":1}\n\n'])
    expect(m).toEqual({ id: '7', event: 'plan.created', data: '{"a":1}' })
  })

  it('tolera mensajes partidos entre chunks y CRLF', () => {
    const msgs = parse(['id: 1\r\nevent: a\r\nda', 'ta: hola\r\n', '\r\nid: 2\nevent: b\ndata: x\n\n'])
    expect(msgs.map((m) => [m.id, m.event, m.data])).toEqual([['1', 'a', 'hola'], ['2', 'b', 'x']])
  })

  it('ignora comentarios keep-alive y une data multilínea', () => {
    const msgs = parse([': keep-alive\n\nevent: x\ndata: l1\ndata: l2\n\n'])
    expect(msgs).toHaveLength(1)
    expect(msgs[0]!.data).toBe('l1\nl2')
  })

  it('el evento `end` del backend llega sin id', () => {
    const msgs = parse(['id: 3\nevent: research.completed\ndata: {}\n\nevent: end\ndata: {}\n\n'])
    expect(msgs[1]!.event).toBe('end')
  })
})

describe('connectSse', () => {
  it('envía Last-Event-ID y la API key, y lee el stream completo', async () => {
    const body = new ReadableStream({
      start(c) {
        c.enqueue(new TextEncoder().encode('id: 5\nevent: e\ndata: {}\n\n'))
        c.close()
      },
    })
    let sentHeaders: Record<string, string> = {}
    const fetchImpl = (async (_u: RequestInfo | URL, init?: RequestInit) => {
      sentHeaders = init?.headers as Record<string, string>
      return new Response(body, { status: 200 })
    }) as typeof fetch
    const got: SseMessage[] = []
    await connectSse('/research/x/events', { lastEventId: 4, signal: new AbortController().signal, onOpen: () => {}, onMessage: (m) => got.push(m) }, fetchImpl)
    expect(sentHeaders['Last-Event-ID']).toBe('4')
    expect(sentHeaders.Accept).toBe('text/event-stream')
    expect(got[0]!.id).toBe('5')
  })

  it('rechaza con ApiError(not_found) si el backend responde 404', async () => {
    const fetchImpl = (async () => new Response(JSON.stringify({ detail: 'Investigación no encontrada' }), { status: 404 })) as typeof fetch
    await expect(
      connectSse('/research/x/events', { signal: new AbortController().signal, onOpen: () => {}, onMessage: () => {} }, fetchImpl),
    ).rejects.toMatchObject({ kind: 'not_found', status: 404 })
  })
})
