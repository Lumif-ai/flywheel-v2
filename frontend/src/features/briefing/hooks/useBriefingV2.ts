import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { BriefingV2Response } from '@/features/briefing/types/briefing-v2'

/**
 * React Query hook for the /briefing/v2 endpoint.
 * Uses query key ['briefing-v2'] (distinct from v1's ['briefing']) to avoid cache collision.
 */
export function useBriefingV2() {
  return useQuery({
    queryKey: ['briefing-v2'],
    queryFn: () => api.get<BriefingV2Response>('/briefing/v2'),
    staleTime: 60_000,
  })
}
