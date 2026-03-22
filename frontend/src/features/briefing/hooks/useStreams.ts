import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PaginatedResponse } from '@/types/api'
import type { WorkStream, WorkStreamDetail } from '@/types/streams'

export function useStreams() {
  return useQuery({
    queryKey: ['streams'],
    queryFn: () =>
      api.get<PaginatedResponse<WorkStream>>('/streams/', {
        params: { limit: 20 },
      }),
  })
}

export function useStreamDetail(id: string) {
  return useQuery({
    queryKey: ['streams', id],
    queryFn: () => api.get<WorkStreamDetail>(`/streams/${id}`),
    enabled: !!id,
  })
}
