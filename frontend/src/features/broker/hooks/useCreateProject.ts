import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createProject } from '../api'
import type { CreateProjectPayload } from '../types/broker'

export function useCreateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateProjectPayload) => createProject(data),

    onSuccess: (_result, vars) => {
      toast.success(`Project created: ${vars.name}`)
    },

    onError: () => {
      toast.error('Failed to create project')
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['broker-projects'] })
      queryClient.invalidateQueries({ queryKey: ['broker-dashboard-stats'] })
    },
  })
}
