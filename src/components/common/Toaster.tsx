import { CheckCircle2, Info, XCircle, X } from 'lucide-react'
import { useToastStore, type ToastKind } from '@/stores/toastStore'

const ICON: Record<ToastKind, typeof Info> = { success: CheckCircle2, error: XCircle, info: Info }

export function Toaster() {
  const { toasts, dismiss } = useToastStore()
  return (
    <div className="toaster" aria-live="polite" aria-atomic="false">
      {toasts.map((t) => {
        const Icon = ICON[t.kind]
        return (
          <div key={t.id} className={`toast ${t.kind}`} role={t.kind === 'error' ? 'alert' : 'status'}>
            <Icon />
            <div className="min-w-0 flex-1"><strong>{t.title}</strong>{t.description && <p>{t.description}</p>}</div>
            <button className="icon-button subtle" style={{ color: '#aaa' }} onClick={() => dismiss(t.id)} aria-label="Cerrar notificación"><X /></button>
          </div>
        )
      })}
    </div>
  )
}
