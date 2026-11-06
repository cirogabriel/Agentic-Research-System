import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import { useDocument } from '@/features/documents/queries'
import type { SourceOut } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatMetric } from '@/utils/format'

interface Props { source: SourceOut; highlighted?: boolean; defaultOpen?: boolean; /** id DOM único (varios informes pueden convivir en un hilo). */ anchorId?: string }

/**
 * Tarjeta de fuente. Los metadatos (título, autor, tipo) se obtienen del documento real (GET /documents/{id});
 * el fragmento es el `snippet` que guardó el backend para esa cita. Si el documento fue eliminado, se indica.
 */
export function SourceCard({ source, highlighted, defaultOpen, anchorId }: Props) {
  const [open, setOpen] = useState(!!defaultOpen)
  useEffect(() => { if (highlighted) setOpen(true) }, [highlighted])
  const doc = useDocument(source.document_id)
  const d = doc.data
  const title = d?.title ?? source.document_name
  const tag = d?.file_type?.toUpperCase() ?? (source.document_id ? '…' : 'ELIMINADO')
  const meta = [source.page_number ? `pág. ${source.page_number}` : null, `relevancia ${formatMetric(source.score)}`].filter(Boolean).join(' · ')
  return (
    <div id={anchorId ?? `src-${source.label}`} className={cn('source-card', highlighted && 'is-target')} style={{ flexWrap: 'wrap' }}>
      <div className="source-icon"><FileText /></div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-xs font-semibold">{title}</p>
          <span className="source-tag">{tag}</span>
          <span className="source-tag" style={{ background: '#efedff', color: '#5b49c6' }}>{source.label}</span>
        </div>
        <p className="mt-1 truncate text-[11px] text-muted-foreground">{[d?.author, source.document_name !== title ? source.document_name : null].filter(Boolean).join(' · ') || (d ? 'Autor no indicado' : '')}</p>
        <p className="mt-1 text-[10px] text-muted-foreground/70">{meta}</p>
      </div>
      <button className="link-accent" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={`${open ? 'Ocultar' : 'Ver'} fragmento de ${source.label}`}>{open ? 'Ocultar' : 'Fragmento'}</button>
      {open && <p className="source-snippet" style={{ width: '100%' }}>{source.snippet || 'El backend no guardó un fragmento para esta fuente.'}</p>}
    </div>
  )
}
