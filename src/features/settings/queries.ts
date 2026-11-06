import { useQuery } from '@tanstack/react-query'
import { systemService } from '@/services/system'

export const useHealth = () => useQuery({ queryKey: ['system', 'health'], queryFn: ({ signal }) => systemService.health(signal), refetchInterval: 30_000, retry: false })
export const useConfiguration = () => useQuery({ queryKey: ['system', 'configuration'], queryFn: ({ signal }) => systemService.configuration(signal), staleTime: 60_000 })
