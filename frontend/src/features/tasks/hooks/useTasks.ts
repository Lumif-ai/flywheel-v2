import { useQuery } from '@tanstack/react-query'
import { queryKeys, fetchTasks } from '../api'
import type { TaskFilters } from '../types/tasks'

export function useTasks(filters?: TaskFilters) {
  return useQuery({
    queryKey: queryKeys.tasks.list(filters),
    queryFn: () => fetchTasks(filters),
    staleTime: 30_000,
  })
}
