import { useQuery } from '@tanstack/react-query'
import { fetchDashboardTasks } from '../api'

export function useDashboardTasks() {
  return useQuery({
    queryKey: ['broker-dashboard-tasks'],
    queryFn: fetchDashboardTasks,
    staleTime: 60_000,
  })
}
