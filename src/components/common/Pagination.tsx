import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function Pagination({ offset, limit, total, onChange }: { offset: number; limit: number; total: number; onChange: (offset: number) => void }) {
  if (total <= limit) return total > 0 ? <div className="pagination"><span>{total} {total === 1 ? 'resultado' : 'resultados'}</span></div> : null
  const from = offset + 1
  const to = Math.min(offset + limit, total)
  return (
    <nav className="pagination" aria-label="Paginación">
      <span>{from}–{to} de {total}</span>
      <div className="row">
        <Button variant="outline" size="xs" onClick={() => onChange(Math.max(0, offset - limit))} disabled={offset === 0} aria-label="Página anterior"><ChevronLeft /></Button>
        <Button variant="outline" size="xs" onClick={() => onChange(offset + limit)} disabled={offset + limit >= total} aria-label="Página siguiente"><ChevronRight /></Button>
      </div>
    </nav>
  )
}
