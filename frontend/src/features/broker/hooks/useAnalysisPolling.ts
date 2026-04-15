import { useQuery } from '@tanstack/react-query'
import { fetchBrokerProject } from '../api'

/**
 * Wraps useBrokerProject with conditional polling.
 * Polls every 10s while analysis_status === 'running', stops otherwise.
 * Uses the same queryKey as useBrokerProject so TanStack deduplicates requests.
 */
export function useAnalysisPolling(projectId: string) {
  return useQuery({
    queryKey: ['broker-project', projectId],
    queryFn: () => fetchBrokerProject(projectId),
    enabled: !!projectId,
    staleTime: 5_000,
    refetchInterval: (query) => {
      const status = query.state.data?.analysis_status
      return status === 'running' ? 10_000 : false
    },
  })
}
