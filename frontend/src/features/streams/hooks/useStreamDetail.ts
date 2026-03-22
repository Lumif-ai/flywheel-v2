import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { WorkStreamDetail } from '@/types/streams'

export function useStreamDetail(id: string) {
  return useQuery({
    queryKey: ['streams', id],
    queryFn: () => api.get<WorkStreamDetail>(`/streams/${id}`),
    enabled: !!id,
  })
}

export function useRenameStream() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.patch<void>(`/streams/${id}`, { name }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['streams'] })
      queryClient.invalidateQueries({ queryKey: ['streams', variables.id] })
    },
  })
}

export function useCreateStream() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      api.post<void>('/streams/', { name, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['streams'] })
    },
  })
}
