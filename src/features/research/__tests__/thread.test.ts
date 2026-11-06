import { describe, expect, it } from 'vitest'
import { buildThread, canFollowUp, groupThreads } from '../thread'
import type { ResearchOut } from '@/types/api'

const r = (id: string, parent: string | null, created: string, status = 'completed'): ResearchOut => ({
  id, parent_id: parent, query: `q-${id}`, status, iterations: 1, tokens_input: 0, tokens_output: 0, cost_usd: 0, created_at: created,
})

describe('thread', () => {
  const a = r('a', null, '2026-01-01'), b = r('b', 'a', '2026-01-02'), c = r('c', 'b', '2026-01-03'), other = r('z', null, '2026-01-04')

  it('une ancestros, actual y descendientes en orden', () => {
    expect(buildThread(b, [a], [a, b, c, other]).map((x) => x.id)).toEqual(['a', 'b', 'c'])
  })
  it('con ramas elige la más antigua y no entra en ciclos', () => {
    const b2 = r('b2', 'a', '2026-01-05')
    expect(buildThread(a, [], [a, b, b2, c]).map((x) => x.id)).toEqual(['a', 'b', 'c'])
    const loop = { ...a, parent_id: 'c' }
    expect(buildThread(loop, [], [loop, b, c]).length).toBeLessThanOrEqual(3)
  })
  it('agrupa hilos y trata los huérfanos como raíz', () => {
    const groups = groupThreads([c, b, a, other])
    expect(groups.map((g) => g.root.id).sort()).toEqual(['a', 'z'])
    expect(groups.find((g) => g.root.id === 'a')!.turns.map((t) => t.id)).toEqual(['a', 'b', 'c'])
  })
  it('solo se puede continuar una investigación completada (memoria del backend = informe previo)', () => {
    expect(canFollowUp(a)).toBe(true)
    expect(canFollowUp(r('x', null, '2026', 'failed'))).toBe(false)
    expect(canFollowUp(undefined)).toBe(false)
  })
})
