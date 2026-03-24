import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useManualSync() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<{ triggered: boolean }>('/email/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-threads'] })
    },
  })
}
