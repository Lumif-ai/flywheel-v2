import { useQuery } from '@tanstack/react-query'
import { fetchGateCounts } from '../api'

export function useGateCounts() {
  return useQuery({
    queryKey: ['broker-gate-counts'],
    queryFn: fetchGateCounts,
    staleTime: 60_000,
    refetchInterval: 30_000,
  })
}
