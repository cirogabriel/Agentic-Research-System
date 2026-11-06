import { describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { buildUrl, configureApiClient, request } from '../client'
import { extractDetail, type ApiError } from '../errors'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('request', () => {
  it('valida la respuesta contra el esquema', async () => {
    const out = await request('/x', { schema: z.object({ a: z.number() }), fetchImpl: (async () => json({ a: 1 })) as typeof fetch })
    expect(out).toEqual({ a: 1 })
  })

  it('devuelve ApiError(contract) si el formato no coincide', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await expect(request('/x', { schema: z.object({ a: z.number() }), fetchImpl: (async () => json({ a: 'no' })) as typeof fetch })).rejects.toMatchObject({ kind: 'contract' })
  })

  it.each([
    [404, 'not_found'], [409, 'conflict'], [422, 'validation'], [402, 'budget'], [500, 'server'],
  ])('mapea HTTP %i a %s', async (status, kind) => {
    await expect(request('/x', { fetchImpl: (async () => json({ detail: 'detalle' }, status)) as typeof fetch })).rejects.toMatchObject({ kind, status })
  })

  it('no expone el cuerpo de un 5xx', async () => {
    const err = (await request('/x', { fetchImpl: (async () => json({ detail: 'Traceback (most recent call last) psycopg...' }, 500)) as typeof fetch }).catch((e: ApiError) => e)) as ApiError
    expect(err.userMessage).not.toMatch(/Traceback|psycopg/)
  })

  it('401 invoca onUnauthorized y envía la API key configurada', async () => {
    const onUnauthorized = vi.fn()
    configureApiClient({ getApiKey: () => 'secreta', onUnauthorized })
    let headers: Record<string, string> = {}
    await expect(request('/x', { fetchImpl: (async (_u: unknown, init?: RequestInit) => { headers = init?.headers as Record<string, string>; return json({ detail: 'x' }, 401) }) as typeof fetch })).rejects.toMatchObject({ kind: 'unauthorized' })
    expect(headers['X-API-Key']).toBe('secreta')
    expect(onUnauthorized).toHaveBeenCalled()
    configureApiClient({ getApiKey: () => null, onUnauthorized: () => {} })
  })

  it('un fallo de red produce ApiError(network) con mensaje comprensible', async () => {
    const err = (await request('/x', { fetchImpl: (async () => { throw new TypeError('Failed to fetch') }) as typeof fetch }).catch((e: ApiError) => e)) as ApiError
    expect(err.kind).toBe('network')
    expect(err.userMessage).toMatch(/backend/)
  })

  it('timeout produce ApiError(timeout)', async () => {
    const fetchImpl = ((_u: unknown, init?: RequestInit) => new Promise((_res, rej) => init?.signal?.addEventListener('abort', () => rej(new DOMException('abort', 'AbortError'))))) as typeof fetch
    await expect(request('/x', { timeoutMs: 10, fetchImpl })).rejects.toMatchObject({ kind: 'timeout' })
  })
})

describe('helpers', () => {
  it('buildUrl repite claves de arrays y omite vacíos', () => {
    const url = buildUrl('/evaluations/experiments/compare', { experiment_ids: ['a', 'b'], dataset_id: undefined, limit: 5 })
    expect(url).toContain('experiment_ids=a&experiment_ids=b')
    expect(url).toContain('limit=5')
    expect(url).not.toContain('dataset_id')
  })
  it('extractDetail formatea errores 422 de FastAPI', () => {
    expect(extractDetail({ detail: [{ loc: ['body', 'query'], msg: 'String should have at least 5 characters' }] })).toBe('query: String should have at least 5 characters')
    expect(extractDetail({ detail: 'hola' })).toBe('hola')
  })
})
