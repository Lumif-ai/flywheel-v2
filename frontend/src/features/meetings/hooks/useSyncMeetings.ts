import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { syncMeetings, queryKeys } from '../api'

export function useSyncMeetings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: syncMeetings,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
      const parts = data.providers
        .filter((p) => !p.error)
        .map((p) => {
          if (p.provider === 'google-calendar') return `Calendar: ${p.events ?? 0} events`
          if (p.provider === 'granola') return `Granola: ${p.synced ?? 0} new`
          return `${p.provider}: synced`
        })
      toast.success(parts.length > 0 ? `Sync complete — ${parts.join(', ')}` : 'Sync complete')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Sync failed')
    },
  })
}
