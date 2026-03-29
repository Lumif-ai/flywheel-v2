import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { queryKeys, createTask } from '../api'
import type { TaskCreate } from '../types/tasks'

export function useCreateTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: TaskCreate) => createTask(body),
    onSuccess: () => {
      toast.success('Task created')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create task')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.summary })
    },
  })
}
