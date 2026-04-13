import { useMutation, useQueryClient } from '@tanstack/react-query'
import { draftRecommendation, editRecommendation, sendRecommendation } from '../api'
import { toast } from 'sonner'

export function useDraftRecommendation(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (recipientEmail?: string) => draftRecommendation(projectId, recipientEmail),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Recommendation draft generated')
    },
    onError: () => toast.error('Failed to generate recommendation draft'),
  })
}

export function useEditRecommendation(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { subject?: string; body?: string; recipient_email?: string }) =>
      editRecommendation(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
    },
    onError: () => toast.error('Failed to update recommendation'),
  })
}

export function useSendRecommendation(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => sendRecommendation(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Recommendation sent')
    },
    onError: () => toast.error('Failed to send recommendation'),
  })
}
