import { useQuery } from '@tanstack/react-query'
import { fetchDashboardStats } from '../api'

export function useDashboardStats() {
  return useQuery({
    queryKey: ['broker-dashboard-stats'],
    queryFn: fetchDashboardStats,
    staleTime: 60_000,
  })
}
