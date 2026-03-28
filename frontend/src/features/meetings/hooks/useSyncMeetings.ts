import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { syncMeetings, queryKeys } from '../api'

export function useSyncMeetings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: syncMeetings,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
      toast.success(
        `Sync complete: ${data.synced} new meetings (${data.skipped} skipped, ${data.already_seen} already seen)`
      )
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Sync failed')
    },
  })
}
