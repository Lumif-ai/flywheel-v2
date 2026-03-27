import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { graduateAccount } from '../api'
import type { GraduatePayload } from '../api'

export function useGraduate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: GraduatePayload) => graduateAccount(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
      queryClient.invalidateQueries({ queryKey: ['relationships'] })
      queryClient.invalidateQueries({ queryKey: ['signals'] })
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      toast.success('Account graduated successfully')
    },
  })
}
