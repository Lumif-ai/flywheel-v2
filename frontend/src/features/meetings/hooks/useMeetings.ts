import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { fetchMeetings, queryKeys } from '../api'
import type { MeetingListItem } from '../types/meetings'

export function useMeetings(status?: string) {
  const user = useAuthStore((s) => s.user)

  return useQuery<MeetingListItem[]>({
    queryKey: queryKeys.meetings.list(status),
    queryFn: async () => {
      const res = await fetchMeetings(status)
      return res.items
    },
    enabled: !!user,
  })
}
