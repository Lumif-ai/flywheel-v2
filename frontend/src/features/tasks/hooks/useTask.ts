import { useQuery } from '@tanstack/react-query'
import { queryKeys, fetchTask } from '../api'

export function useTask(taskId: string | null) {
  return useQuery({
    queryKey: queryKeys.tasks.detail(taskId!),
    queryFn: () => fetchTask(taskId!),
    enabled: !!taskId,
  })
}
