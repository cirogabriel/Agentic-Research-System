import { QueryClient } from '@tanstack/react-query';
import { isApiError } from '@/services/api';

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        refetchOnWindowFocus: false,
        
        retry: (count, error) =>
          isApiError(error) ? error.retryable && count < 2 : count < 1,
      },
      mutations: { retry: false },
    },
  });
}
