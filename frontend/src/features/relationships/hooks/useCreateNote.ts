import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createNote, queryKeys } from '../api'

export function useCreateNote() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      createNote(id, content),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.relationships.detail(variables.id),
      })
    },
  })
}
