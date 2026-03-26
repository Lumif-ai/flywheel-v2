import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchTimeline } from '../api'

export function useTimeline(accountId: string, params: { offset?: number; limit?: number }) {
  return useQuery({
    queryKey: ['timeline', accountId, params],
    queryFn: () => fetchTimeline(accountId, params),
    enabled: !!accountId,
    placeholderData: keepPreviousData,
  })
}
