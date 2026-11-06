import { useState, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { configureApiClient } from '@/services/api'
import { useConnectionStore } from '@/stores/connectionStore'
import { createQueryClient } from './queryClient'

// Conecta el cliente HTTP con el estado de la app (clave y aviso de autenticación) una sola vez.
configureApiClient({
  getApiKey: () => useConnectionStore.getState().apiKey,
  onUnauthorized: () => useConnectionStore.getState().markAuthRequired(),
})

export function Providers({ children, client }: { children: ReactNode; client?: ReturnType<typeof createQueryClient> }) {
  const [qc] = useState(() => client ?? createQueryClient())
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}
