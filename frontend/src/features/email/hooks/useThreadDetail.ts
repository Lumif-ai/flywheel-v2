import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ThreadDetailResponse } from '../types/email'

export function useThreadDetail(threadId: string | null) {
  return useQuery({
    queryKey: ['thread-detail', threadId],
    queryFn: () => api.get<ThreadDetailResponse>(`/email/threads/${threadId}`),
    enabled: !!threadId,
    staleTime: 30_000,
  })
}
