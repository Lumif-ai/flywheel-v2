import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { fetchMeetingDetail, queryKeys } from '../api'
import type { MeetingDetail } from '../types/meetings'

export function useMeetingDetail(id: string | undefined) {
  const user = useAuthStore((s) => s.user)

  return useQuery<MeetingDetail>({
    queryKey: queryKeys.meetings.detail(id ?? ''),
    queryFn: () => fetchMeetingDetail(id!),
    enabled: !!user && !!id,
  })
}
