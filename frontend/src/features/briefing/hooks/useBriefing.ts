import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { BriefingResponse } from '@/types/streams'

export function useBriefing() {
  return useQuery({
    queryKey: ['briefing'],
    queryFn: () => api.get<BriefingResponse>('/briefing'),
    staleTime: 60_000,
  })
}
