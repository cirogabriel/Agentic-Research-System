import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { EmptyState, QueryBoundary } from '@/components/common/States'
import { Pagination } from '@/components/common/Pagination'
import { StatusBadge } from '@/components/common/StatusBadge'
import { DocumentDrawer } from '@/features/documents/DocumentDrawer'
import { useDocuments } from '@/features/documents/queries'
import { UploadPanel } from '@/features/documents/UploadPanel'
import { DEFAULT_MAX_UPLOAD_MB } from '@/features/documents/validation'
import { useConfiguration } from '@/features/settings/queries'
import { DOCUMENT_STATUSES } from '@/types/api'
import { documentStatusMeta, formatBytes, formatDateTime } from '@/utils/format'

const LIMIT = 15
const TYPES = ['pdf', 'docx', 'txt', 'md', 'html']

export function DocumentsPage() {
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState('')
  const [fileType, setFileType] = useState('')
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const config = useConfiguration()
  const maxMb = typeof config.data?.max_upload_mb === 'number' ? config.data.max_upload_mb : DEFAULT_MAX_UPLOAD_MB
  const { data, isLoading, error, refetch } = useDocuments({ limit: LIMIT, offset, status: status || undefined, file_type: fileType || undefined })
  const items = useMemo(() => (data?.items ?? []).filter((d) => `${d.title ?? ''} ${d.filename} ${d.author ?? ''}`.toLowerCase().includes(q.trim().toLowerCase())), [data, q])
  const reset = (fn: () => void) => { fn(); setOffset(0) }

  return (
    <div className="page">
      <div className="page-header"><div><p className="eyebrow">Conocimiento</p><h1>Documentos</h1><p className="muted-copy">Los documentos indexados alimentan la recuperación (RAG) de tus investigaciones.</p></div></div>
      <UploadPanel maxMb={maxMb} />
      <div className="panel">
        <div className="toolbar">
          <div className="search-box"><Search /><input className="input" type="search" placeholder="Buscar en esta página…" aria-label="Buscar documentos" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <select className="select" aria-label="Filtrar por estado" value={status} onChange={(e) => reset(() => setStatus(e.target.value))}>
            <option value="">Todos los estados</option>
            {DOCUMENT_STATUSES.map((s) => <option key={s} value={s}>{documentStatusMeta(s).label}</option>)}
          </select>
          <select className="select" aria-label="Filtrar por tipo" value={fileType} onChange={(e) => reset(() => setFileType(e.target.value))}>
            <option value="">Todos los tipos</option>
            {TYPES.map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select>
        </div>
        <QueryBoundary isLoading={isLoading} error={error} onRetry={() => void refetch()} isEmpty={items.length === 0}
          empty={<EmptyState title={q || status || fileType ? 'Sin resultados' : 'Aún no hay documentos'} description={q || status || fileType ? 'Prueba con otros filtros.' : 'Sube PDF, DOCX, TXT, Markdown o HTML para empezar a investigar sobre ellos.'} />}>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Documento</th><th>Tipo</th><th>Estado</th><th className="num">Chunks</th><th className="num">Tamaño</th><th>Subido</th></tr></thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id} className="is-clickable" tabIndex={0} onClick={() => setSelected(d.id)} onKeyDown={(e) => { if (e.key === 'Enter') setSelected(d.id) }} aria-label={`Ver detalle de ${d.filename}`}>
                    <td><div className="cell-title">{d.title ?? d.filename}</div><div className="hint">{d.author ?? d.filename}</div></td>
                    <td>{d.file_type.toUpperCase()}</td>
                    <td><StatusBadge meta={documentStatusMeta(d.status)} /></td>
                    <td className="num">{d.num_chunks}</td>
                    <td className="num">{formatBytes(d.size_bytes)}</td>
                    <td>{formatDateTime(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination offset={offset} limit={LIMIT} total={data?.total ?? 0} onChange={setOffset} />
        </QueryBoundary>
      </div>
      {selected && <DocumentDrawer id={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
