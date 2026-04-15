import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { draftRecommendation, editRecommendation, sendRecommendation, fetchProjectRecommendations } from '../api'
import { toast } from 'sonner'

export function useProjectRecommendation(projectId: string) {
  return useQuery({
    queryKey: ['broker', 'recommendations', projectId],
    queryFn: () => fetchProjectRecommendations(projectId),
    enabled: !!projectId,
    staleTime: 15_000,
    select: (data) => data.items[0] ?? null,
  })
}

export function useDraftRecommendation(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (recipientEmail?: string) => draftRecommendation(projectId, recipientEmail),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      qc.invalidateQueries({ queryKey: ['broker', 'recommendations', projectId] })
      toast.success('Recommendation draft generated')
    },
    onError: () => toast.error('Failed to generate recommendation draft'),
  })
}

export function useEditRecommendation(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ recommendationId, data }: { recommendationId: string; data: { subject?: string; body?: string; recipient_email?: string } }) =>
      editRecommendation(recommendationId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      qc.invalidateQueries({ queryKey: ['broker', 'recommendations', projectId] })
    },
    onError: () => toast.error('Failed to update recommendation'),
  })
}

export function useSendRecommendation(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (recommendationId: string) => sendRecommendation(recommendationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      qc.invalidateQueries({ queryKey: ['broker', 'recommendations', projectId] })
      toast.success('Recommendation sent')
    },
    onError: () => toast.error('Failed to send recommendation'),
  })
}
