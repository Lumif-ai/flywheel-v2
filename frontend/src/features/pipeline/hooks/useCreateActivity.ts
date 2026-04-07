import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createActivity } from '../api'

interface MutationVars {
  entryId: string
  data: {
    type: string
    channel?: string
    status?: string
    subject?: string
    body_preview?: string
    contact_id?: string
    metadata_?: Record<string, unknown>
  }
}

export function useCreateActivity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ entryId, data }: MutationVars) =>
      createActivity(entryId, data),

    onSuccess: () => {
      toast.success('New step created')
    },

    onError: () => {
      toast.error('Failed to create step')
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      queryClient.invalidateQueries({ queryKey: ['contact-activities'] })
    },
  })
}
