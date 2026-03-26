import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { graduateAccount } from '../api'

export function useGraduate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (accountId: string) => graduateAccount(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      toast.success('Account graduated to Engaged')
    },
  })
}
