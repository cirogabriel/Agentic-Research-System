import { QueryClient } from '@tanstack/react-query'
import { isApiError } from '@/services/api'

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        refetchOnWindowFocus: false,
        // Solo se reintentan fallos transitorios (red, timeout, 5xx); un 404/409/422 no mejora al repetirse.
        retry: (count, error) => (isApiError(error) ? error.retryable && count < 2 : count < 1),
      },
      mutations: { retry: false },
    },
  })
}
