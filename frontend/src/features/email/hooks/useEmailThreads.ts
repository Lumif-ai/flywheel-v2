import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ThreadListResponse } from '../types/email'

interface UseEmailThreadsParams {
  priority_min?: number
  offset?: number
  limit?: number
}

export function useEmailThreads(params?: UseEmailThreadsParams) {
  return useQuery({
    queryKey: ['email-threads', params],
    queryFn: () =>
      api.get<ThreadListResponse>('/email/threads', {
        params: params as Record<string, unknown> | undefined,
      }),
    staleTime: 30_000,
  })
}
