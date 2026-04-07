import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { patchActivity } from '../api'

interface MutationVars {
  entryId: string
  activityId: string
  data: Record<string, unknown>
}

export function useActivityMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ entryId, activityId, data }: MutationVars) =>
      patchActivity(entryId, activityId, data),

    onSuccess: (_result, { data }) => {
      if (data.status) {
        toast.success('Activity updated')
      }
    },

    onError: () => {
      toast.error('Failed to update activity')
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      queryClient.invalidateQueries({ queryKey: ['contact-activities'] })
      queryClient.invalidateQueries({ queryKey: ['pipeline-detail'] })
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
    },
  })
}
