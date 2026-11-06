import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info'
export interface Toast {
  id: number
  kind: ToastKind
  title: string
  description?: string
  at: number
}

interface ToastState {
  toasts: Toast[] // visibles
  history: Toast[] // centro de notificaciones (campana)
  push: (kind: ToastKind, title: string, description?: string) => void
  dismiss: (id: number) => void
  clearHistory: () => void
}

let seq = 0
export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  history: [],
  push: (kind, title, description) => {
    const toast: Toast = { id: ++seq, kind, title, description, at: Date.now() }
    set((s) => ({ toasts: [...s.toasts, toast].slice(-4), history: [toast, ...s.history].slice(0, 30) }))
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== toast.id) })), kind === 'error' ? 8000 : 4500)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clearHistory: () => set({ history: [] }),
}))

export const notify = {
  success: (title: string, description?: string) => useToastStore.getState().push('success', title, description),
  error: (title: string, description?: string) => useToastStore.getState().push('error', title, description),
  info: (title: string, description?: string) => useToastStore.getState().push('info', title, description),
}
