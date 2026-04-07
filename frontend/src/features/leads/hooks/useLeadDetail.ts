import { useQuery } from '@tanstack/react-query'
import { fetchLeadDetail } from '../api'

export function useLeadDetail(id: string | null) {
  return useQuery({
    queryKey: ['lead-detail', id],
    queryFn: () => fetchLeadDetail(id!),
    enabled: !!id,
  })
}
