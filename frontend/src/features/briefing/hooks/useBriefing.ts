import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { BriefingResponse } from '@/types/streams'

export function useBriefing() {
  return useQuery({
    queryKey: ['briefing'],
    queryFn: () => api.get<BriefingResponse>('/briefing'),
    staleTime: 60_000,
  })
}

export function useDismissCard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: {
      card_type: string
      suggestion_key: string
      feedback?: string
    }) =>
      api.post<{ dismissed: boolean }>('/briefing/dismiss', {
        card_type: params.card_type,
        suggestion_key: params.suggestion_key,
        feedback: params.feedback ?? 'not_relevant',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
    },
  })
}
