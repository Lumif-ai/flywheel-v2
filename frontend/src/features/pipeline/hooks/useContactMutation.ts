import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { patchContact } from '../api'

interface MutationVars {
  entryId: string
  contactId: string
  data: Record<string, unknown>
}

export function useContactMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ entryId, contactId, data }: MutationVars) =>
      patchContact(entryId, contactId, data),

    onError: () => {
      toast.error('Failed to update contact')
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      queryClient.invalidateQueries({ queryKey: ['contact-activities'] })
    },
  })
}
