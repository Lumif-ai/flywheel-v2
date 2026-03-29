import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { queryKeys, updateTaskStatus } from '../api'
import type { TasksListResponse } from '../types/tasks'

export function useUpdateTaskStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateTaskStatus(id, status),

    onMutate: async ({ id }) => {
      // Cancel outgoing refetches so they don't overwrite our optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all })

      // Snapshot previous task list for rollback (only list queries, NOT summary)
      const previousList = queryClient.getQueriesData<TasksListResponse>({
        queryKey: ['tasks', 'list'],
      })

      // Optimistically remove the task from task list queries
      queryClient.setQueriesData<TasksListResponse>(
        { queryKey: ['tasks', 'list'] },
        (old) => {
          if (!old?.tasks) return old
          return {
            ...old,
            tasks: old.tasks.filter((t) => t.id !== id),
            total: old.total - 1,
          }
        },
      )

      return { previousList }
    },

    onError: (_error, _variables, context) => {
      // Rollback to snapshot
      if (context?.previousList) {
        for (const [key, data] of context.previousList) {
          queryClient.setQueryData(key, data)
        }
      }
      toast.error('Could not update task. Please try again.')
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.summary })
    },
  })
}
