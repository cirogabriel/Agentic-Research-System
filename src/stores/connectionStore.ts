import { create } from 'zustand'

const KEY = 'ars.apiKey'
const read = (): string | null => {
  try { return sessionStorage.getItem(KEY) } catch { return null }
}

interface ConnectionState {
  apiKey: string | null
  /** Se activa cuando el backend respondió 401: la UI muestra un aviso para configurar la API key. */
  authRequired: boolean
  setApiKey: (key: string | null) => void
  markAuthRequired: () => void
}

/** La API key vive solo en sessionStorage (se borra al cerrar la pestaña) y nunca se incluye en el bundle. */
export const useConnectionStore = create<ConnectionState>((set) => ({
  apiKey: read(),
  authRequired: false,
  setApiKey: (key) => {
    try {
      if (key) sessionStorage.setItem(KEY, key)
      else sessionStorage.removeItem(KEY)
    } catch { /* almacenamiento no disponible */ }
    set({ apiKey: key, authRequired: false })
  },
  markAuthRequired: () => set({ authRequired: true }),
}))
