import { Link } from 'react-router-dom'
import { LoadingState } from '@/components/common/States'
import { useDocuments } from '@/features/documents/queries'

/** Restringe la investigación a documentos concretos mediante `options.document_ids` (solo documentos indexados). */
export function DocumentScope({ selected, onChange }: { selected: string[]; onChange: (ids: string[]) => void }) {
  const { data, isLoading, error } = useDocuments({ limit: 100, offset: 0, status: 'indexed' })
  if (isLoading) return <LoadingState label="Cargando documentos" />
  if (error) return <p className="field-error">No se pudieron cargar los documentos.</p>
  const items = data?.items ?? []
  if (items.length === 0)
    return <p className="text-sm-muted">No hay documentos indexados. <Link to="/documents" className="link-accent">Sube documentos</Link> para poder limitar la búsqueda.</p>
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <span className="text-sm-muted">{selected.length === 0 ? 'Se buscará en todos los documentos indexados' : `${selected.length} seleccionado(s)`}</span>
        {selected.length > 0 && <button type="button" className="link-accent spacer" onClick={() => onChange([])}>Quitar filtro</button>}
      </div>
      <div className="doc-pick" role="group" aria-label="Documentos a consultar">
        {items.map((d) => (
          <label key={d.id} className="check" style={{ padding: '4px 0' }}>
            <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
            <span className="truncate">{d.title ?? d.filename}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
