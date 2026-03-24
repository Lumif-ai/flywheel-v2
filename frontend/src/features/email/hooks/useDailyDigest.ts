import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { DigestResponse } from '../types/email'

export function useDailyDigest() {
  return useQuery({
    queryKey: ['email-digest'],
    queryFn: () => api.get<DigestResponse>('/email/digest'),
    staleTime: 5 * 60_000, // Digest data changes slowly — 5 min stale time
  })
}
