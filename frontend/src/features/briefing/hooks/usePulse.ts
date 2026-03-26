import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PulseResponse } from '../types/pulse'

export function usePulse(limit = 5) {
  return useQuery({
    queryKey: ['pulse', limit],
    queryFn: () => api.get<PulseResponse>('/pulse/', { params: { limit } }),
  })
}
