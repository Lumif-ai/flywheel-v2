import { useQuery } from '@tanstack/react-query'
import { queryKeys, fetchTaskSummary } from '../api'

export function useTaskSummary() {
  return useQuery({
    queryKey: queryKeys.tasks.summary,
    queryFn: fetchTaskSummary,
    staleTime: 30_000,
  })
}
