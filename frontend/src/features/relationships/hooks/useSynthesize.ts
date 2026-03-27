import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { synthesize, queryKeys } from '../api'
import type { ApiError } from '@/lib/api'

export function useSynthesize() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => synthesize(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.relationships.detail(id),
      })
    },
    onError: (error: ApiError, _id) => {
      if (error.code === 429) {
        toast.error('AI summary was refreshed recently. Try again in a few minutes.')
      }
    },
  })
}
