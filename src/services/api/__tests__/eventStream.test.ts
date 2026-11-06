import { describe, expect, it, vi } from 'vitest'
import { runEventStream, type ConnectFn, type StreamStatus } from '../eventStream'
import { ApiError } from '../errors'
import type { SseMessage } from '../sse'
import type { ResearchEvent } from '@/types/events'

const msg = (id: number, type = 'task.started'): SseMessage => ({ id: String(id), event: type, data: JSON.stringify({ type, message: `m${id}`, payload: {}, at: '2026-01-01T00:00:00Z' }) })
const end: SseMessage = { event: 'end', data: '{}' }
const noSleep = async () => {}

function setup(connect: ConnectFn, extra: Partial<Parameters<typeof runEventStream>[0]> = {}) {
  const events: ResearchEvent[] = []
  const statuses: StreamStatus[] = []
  const errors: unknown[] = []
  const done = runEventStream({ connect, onEvent: (e) => events.push(e), onStatus: (s) => statuses.push(s), onError: (e) => errors.push(e), signal: new AbortController().signal, sleep: noSleep, ...extra })
  return { events, statuses, errors, done }
}

describe('runEventStream', () => {
  it('entrega los eventos en orden y termina al recibir `end`', async () => {
    const { events, statuses, done } = setup(async (o) => { o.onOpen(); o.onMessage(msg(1)); o.onMessage(msg(2)); o.onMessage(end) })
    await done
    expect(events.map((e) => e.id)).toEqual([1, 2])
    expect(statuses.at(-1)).toBe('ended')
  })

  it('reconecta tras una caída con Last-Event-ID y sin duplicar mensajes', async () => {
    const seenLast: (number | undefined)[] = []
    let call = 0
    const { events, statuses, done } = setup(async (o) => {
      seenLast.push(o.lastEventId)
      call += 1
      o.onOpen()
      if (call === 1) {
        o.onMessage(msg(1)); o.onMessage(msg(2))
        throw new ApiError('network', 'caída')
      }
      // El servidor reenvía el evento 2 (repetido) antes de los nuevos
      o.onMessage(msg(2)); o.onMessage(msg(3)); o.onMessage(end)
    })
    await done
    expect(seenLast).toEqual([undefined, 2])
    expect(events.map((e) => e.id)).toEqual([1, 2, 3])
    expect(statuses).toContain('reconnecting')
    expect(statuses.at(-1)).toBe('ended')
  })

  it('reconecta si el servidor cierra el stream sin `end`', async () => {
    let call = 0
    const { events, done } = setup(async (o) => { call += 1; o.onOpen(); if (call === 1) o.onMessage(msg(1)); else { o.onMessage(msg(2)); o.onMessage(end) } })
    await done
    expect(events.map((e) => e.id)).toEqual([1, 2])
  })

  it('falla tras agotar los reintentos', async () => {
    const connect = vi.fn(async () => { throw new ApiError('network', 'sin red') })
    const { statuses, errors, done } = setup(connect, { maxRetries: 2 })
    await done
    expect(connect).toHaveBeenCalledTimes(3)
    expect(statuses.at(-1)).toBe('failed')
    expect(errors).toHaveLength(1)
  })

  it('no reintenta ante 404/401 (error no transitorio)', async () => {
    const connect = vi.fn(async () => { throw new ApiError('not_found', 'no existe', 404) })
    const { statuses, done } = setup(connect)
    await done
    expect(connect).toHaveBeenCalledTimes(1)
    expect(statuses.at(-1)).toBe('failed')
  })

  it('ignora mensajes malformados sin romper el stream', async () => {
    const { events, done } = setup(async (o) => { o.onMessage({ id: '1', event: 'x', data: 'no-json' }); o.onMessage(msg(2)); o.onMessage(end) })
    await done
    expect(events.map((e) => e.id)).toEqual([2])
  })

  it('se detiene silenciosamente si se aborta', async () => {
    const ac = new AbortController()
    const connect = vi.fn(async () => { ac.abort(); throw new ApiError('aborted', 'cancelado') })
    const events: ResearchEvent[] = []
    await runEventStream({ connect, onEvent: (e) => events.push(e), onStatus: () => {}, signal: ac.signal, sleep: noSleep })
    expect(connect).toHaveBeenCalledTimes(1)
  })
})
