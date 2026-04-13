import { useQuery } from '@tanstack/react-query'
import { fetchBrokerProject } from '../api'

export function useBrokerProject(projectId: string) {
  return useQuery({
    queryKey: ['broker-project', projectId],
    queryFn: () => fetchBrokerProject(projectId),
    staleTime: 15_000,
    enabled: !!projectId,
  })
}
