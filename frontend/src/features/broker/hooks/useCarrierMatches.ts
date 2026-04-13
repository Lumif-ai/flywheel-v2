import { useQuery } from '@tanstack/react-query'
import { fetchCarrierMatches } from '../api'

export function useCarrierMatches(projectId: string) {
  return useQuery({
    queryKey: ['carrier-matches', projectId],
    queryFn: () => fetchCarrierMatches(projectId),
    staleTime: 15_000,
    enabled: !!projectId,
  })
}
