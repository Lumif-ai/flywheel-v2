import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { queryKeys, updateTask } from '../api'
import type { TaskUpdate } from '../types/tasks'

export function useUpdateTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: TaskUpdate }) =>
      updateTask(id, body),
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update task')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.summary })
    },
  })
}
