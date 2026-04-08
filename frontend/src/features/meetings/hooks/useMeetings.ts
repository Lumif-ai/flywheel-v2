import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { fetchMeetings, queryKeys } from '../api'
import type { MeetingListItem } from '../types/meetings'

export function useMeetings(params?: { status?: string; time?: string; show_hidden?: boolean }) {
  const user = useAuthStore((s) => s.user)

  return useQuery<MeetingListItem[]>({
    queryKey: [...queryKeys.meetings.list(params), params?.show_hidden ?? false],
    queryFn: async () => {
      const res = await fetchMeetings(params)
      return res.items
    },
    enabled: !!user,
  })
}
