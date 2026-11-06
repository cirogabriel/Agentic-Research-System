import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  side?: boolean
  description?: string
}

/** Diálogo accesible: role=dialog, Escape y clic en el fondo cierran, foco inicial dentro y restauración al cerrar. */
export function Modal({ title, onClose, children, side, description }: ModalProps) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.() }
  }, [onClose])
  return (
    <div className={`modal-backdrop ${side ? 'side' : ''}`} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className={`modal ${side ? 'side' : ''}`}>
        <div className="modal-head">
          <div><h2>{title}</h2>{description && <p className="panel-sub">{description}</p>}</div>
          <button className="icon-button" onClick={onClose} aria-label="Cerrar"><X /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  title, description, confirmLabel, danger, busy, onConfirm, onClose,
}: { title: string; description: ReactNode; confirmLabel: string; danger?: boolean; busy?: boolean; onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal title={title} onClose={onClose}>
      <div className="text-sm-muted" style={{ fontSize: 12 }}>{description}</div>
      <div className="modal-actions">
        <Button variant="outline" onClick={onClose} disabled={busy}>Cancelar</Button>
        <Button variant={danger ? 'destructive' : 'default'} onClick={onConfirm} disabled={busy}>{busy ? 'Procesando…' : confirmLabel}</Button>
      </div>
    </Modal>
  )
}
