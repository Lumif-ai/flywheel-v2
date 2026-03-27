import { useMutation } from '@tanstack/react-query'
import { askRelationship } from '../api'

export function useAsk() {
  return useMutation({
    mutationFn: ({ id, question }: { id: string; question: string }) =>
      askRelationship(id, question),
    // No cache invalidation — ask is stateless Q&A (does not write to the account)
  })
}
