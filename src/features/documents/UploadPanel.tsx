import { useCallback, useRef, useState, type DragEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileText, UploadCloud, XCircle } from 'lucide-react'
import { documentsService } from '@/services/documents'
import { toUserMessage } from '@/services/api'
import { notify } from '@/stores/toastStore'
import { formatBytes } from '@/utils/format'
import { cn } from '@/utils/cn'
import { documentKeys } from './queries'
import { validateFile } from './validation'

type ItemState = 'uploading' | 'done' | 'error'
interface QueueItem { key: number; name: string; size: number; state: ItemState; message?: string }
const ACTION_LABEL = { created: 'Subido. Indexando…', updated: 'Nueva versión subida. Indexando…', duplicate: 'Ya existía un documento idéntico.' } as const
let seq = 0

export function UploadPanel({ maxMb }: { maxMb: number }) {
  const qc = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [busy, setBusy] = useState(false)
  const patch = (key: number, p: Partial<QueueItem>) => setQueue((q) => q.map((i) => (i.key === key ? { ...i, ...p } : i)))

  const handleFiles = useCallback(async (files: File[]) => {
    if (!files.length) return
    const items = files.map((f) => ({ file: f, key: ++seq, error: validateFile(f, maxMb) }))
    setQueue((q) => [...items.map<QueueItem>((i) => ({ key: i.key, name: i.file.name, size: i.file.size, state: i.error ? 'error' : 'uploading', message: i.error ?? 'Subiendo…' })), ...q].slice(0, 30))
    setBusy(true)
    let ok = 0
    // En serie: cada subida dispara parseo, chunking y embeddings en el backend.
    for (const i of items.filter((x) => !x.error)) {
      try {
        const r = await documentsService.upload(i.file)
        patch(i.key, { state: 'done', message: ACTION_LABEL[r.action] })
        ok += 1
      } catch (e) {
        patch(i.key, { state: 'error', message: toUserMessage(e) })
      }
    }
    setBusy(false)
    if (ok) notify.success(`${ok} documento(s) enviado(s)`, 'La indexación continúa en segundo plano.')
    void qc.invalidateQueries({ queryKey: documentKeys.all })
  }, [maxMb, qc])

  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); void handleFiles(Array.from(e.dataTransfer.files)) }

  return (
    <div className="panel">
      <div
        className={cn('dropzone', over && 'is-over', busy && 'is-disabled')} role="button" tabIndex={0} aria-label="Zona para soltar o seleccionar documentos"
        onClick={() => input.current?.click()} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.current?.click() } }}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={onDrop}
      >
        <UploadCloud size={26} color="#6659bd" />
        <strong style={{ fontSize: 13 }}>Arrastra documentos aquí o haz clic para seleccionarlos</strong>
        <span className="text-sm-muted">PDF, DOCX, TXT, Markdown o HTML · hasta {maxMb} MB por archivo</span>
        <input ref={input} type="file" hidden multiple accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm" data-testid="file-input"
          onChange={(e) => { void handleFiles(Array.from(e.target.files ?? [])); e.target.value = '' }} />
      </div>
      {queue.length > 0 && (
        <div style={{ marginTop: 12 }} aria-live="polite">
          <div className="row" style={{ marginBottom: 4 }}><strong style={{ fontSize: 11 }}>Archivos seleccionados</strong><button className="link-accent spacer" onClick={() => setQueue((q) => q.filter((i) => i.state === 'uploading'))}>Limpiar</button></div>
          {queue.map((i) => (
            <div className="file-row" key={i.key}>
              {i.state === 'uploading' ? <span className="spinner" /> : i.state === 'done' ? <CheckCircle2 size={16} color="#3f8a63" /> : <XCircle size={16} color="#b4423a" />}
              <FileText size={14} color="#9a97a1" />
              <div className="min-w-0 flex-1"><div className="truncate" style={{ fontWeight: 600 }}>{i.name} <span className="hint">{formatBytes(i.size)}</span></div><div className={i.state === 'error' ? 'field-error' : 'hint'}>{i.message}</div></div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
