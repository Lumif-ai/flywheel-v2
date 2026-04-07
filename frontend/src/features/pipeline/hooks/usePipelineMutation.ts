import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { patchPipelineEntry } from '../api'
import type { PipelineResponse } from '../types/pipeline'

interface MutationVars {
  id: string
  data: Record<string, unknown>
}

export function usePipelineMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: MutationVars) => patchPipelineEntry(id, data),

    onMutate: async ({ id, data }) => {
      // Cancel outgoing pipeline queries to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['pipeline'] })

      // Snapshot all current pipeline query caches
      const previousQueries = queryClient.getQueriesData<PipelineResponse>({
        queryKey: ['pipeline'],
      })

      // Optimistically update matching item in all cached results
      queryClient.setQueriesData<PipelineResponse>(
        { queryKey: ['pipeline'] },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((item) =>
              item.id === id ? { ...item, ...data } : item,
            ),
          }
        },
      )

      return { previousQueries }
    },

    onError: (_err, _vars, context) => {
      // Revert to snapshot on failure
      if (context?.previousQueries) {
        for (const [queryKey, data] of context.previousQueries) {
          queryClient.setQueryData(queryKey, data)
        }
      }
      toast.error('Failed to update')
    },

    onSettled: () => {
      // Refetch pipeline queries to ensure consistency
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
      // Also invalidate side panel detail cache so inline edits update the panel
      queryClient.invalidateQueries({ queryKey: ['pipeline-detail'] })
    },
  })
}
