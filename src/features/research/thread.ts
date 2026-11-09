import type { ResearchOut } from '@/types/api';


export function buildThread(
  current: ResearchOut,
  ancestors: ResearchOut[],
  all: readonly ResearchOut[],
): ResearchOut[] {
  const seen = new Set<string>([...ancestors.map((a) => a.id), current.id]);
  const chain: ResearchOut[] = [...ancestors, current];
  let cursor = current;
  for (;;) {
    const next = all
      .filter((r) => r.parent_id === cursor.id && !seen.has(r.id))
      .sort((a, b) => a.created_at.localeCompare(b.created_at))[0];
    if (!next) break;
    seen.add(next.id);
    chain.push(next);
    cursor = next;
  }
  return chain;
}


export function groupThreads(
  items: readonly ResearchOut[],
): { root: ResearchOut; turns: ResearchOut[] }[] {
  const ids = new Set(items.map((i) => i.id));
  const roots = items.filter((i) => !i.parent_id || !ids.has(i.parent_id));
  return roots.map((root) => ({ root, turns: buildThread(root, [], items) }));
}

export const canFollowUp = (turn: ResearchOut | undefined): boolean =>
  turn?.status === 'completed';
