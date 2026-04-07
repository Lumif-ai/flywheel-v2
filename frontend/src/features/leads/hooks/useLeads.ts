import { useQuery } from '@tanstack/react-query'
import { fetchLeads } from '../api'
import type { LeadParams } from '../types/lead'

export function useLeads(params: LeadParams) {
  return useQuery({
    queryKey: ['leads', params],
    queryFn: () => fetchLeads(params),
    placeholderData: (prev) => prev,
  })
}
