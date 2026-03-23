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

export function useClassifyMeeting() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: { work_item_id: string; stream_id: string }) =>
      api.post<{ classified: boolean; stream_name: string }>(
        '/briefing/classify-meeting',
        params,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
    },
  })
}

export function useNudgeDismiss() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: { nudge_type: string; nudge_key: string }) =>
      api.post<{ dismissed: boolean }>('/briefing/nudge/dismiss', params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
    },
  })
}

export function useNudgeSubmit() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: { nudge_key: string; stream_id: string; text: string }) =>
      api.post<{ submitted: boolean; entry_id: string }>(
        '/briefing/nudge/submit',
        params,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
      queryClient.invalidateQueries({ queryKey: ['streams'] })
    },
  })
}

export function useNudgeResearch() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: {
      nudge_key: string
      entity_id: string
      entity_name: string
    }) =>
      api.post<{ triggered: boolean; work_item_id: string }>(
        '/briefing/nudge/research',
        params,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
    },
  })
}
