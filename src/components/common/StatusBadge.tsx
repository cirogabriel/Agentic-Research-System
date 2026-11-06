import type { StatusMeta } from '@/utils/format'

export function StatusBadge({ meta }: { meta: StatusMeta }) {
  return <span className={`badge ${meta.tone}`}>{meta.label}</span>
}
