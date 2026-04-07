import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createPipelineEntry } from '../api'

interface CreateVars {
  name: string
  entity_type?: string
  domain?: string
}

export function usePipelineCreate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateVars) => createPipelineEntry(data),

    onSuccess: (result, vars) => {
      if (result.dedup_matched) {
        toast.info(`Found existing entry: ${vars.name}`)
      } else {
        toast.success(`Created: ${vars.name}`)
      }
    },

    onError: () => {
      toast.error('Failed to create entry')
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
    },
  })
}
