import { useQuery } from '@tanstack/react-query'
import { fetchSolicitationDrafts } from '../api'

export function useSolicitationDrafts(projectId: string) {
  return useQuery({
    queryKey: ['broker', 'solicitation-drafts', projectId],
    queryFn: () => fetchSolicitationDrafts(projectId),
    enabled: !!projectId,
    staleTime: 15_000,
  })
}
