import { useQuery } from '@tanstack/react-query'
import { fetchLeadsPipeline } from '../api'

export function useLeadsPipeline() {
  return useQuery({
    queryKey: ['leads-pipeline'],
    queryFn: fetchLeadsPipeline,
  })
}
