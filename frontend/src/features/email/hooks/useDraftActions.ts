import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { RegenerateRequest, RegenerateDraftResponse } from '../types/email'

export function useApproveDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ draftId }: { draftId: string }) =>
      api.post<{ approved: boolean }>(`/email/drafts/${draftId}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-threads'] })
      queryClient.invalidateQueries({ queryKey: ['thread-detail'] })
    },
  })
}

export function useDismissDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ draftId }: { draftId: string }) =>
      api.post<{ dismissed: boolean }>(`/email/drafts/${draftId}/dismiss`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-threads'] })
      queryClient.invalidateQueries({ queryKey: ['thread-detail'] })
    },
  })
}

export function useEditDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ draftId, draft_body }: { draftId: string; draft_body: string }) =>
      api.put<{ updated: boolean }>(`/email/drafts/${draftId}`, { draft_body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-threads'] })
      queryClient.invalidateQueries({ queryKey: ['thread-detail'] })
    },
  })
}

export function useRegenerateDraft(draftId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: RegenerateRequest) =>
      api.post<RegenerateDraftResponse>(`/email/drafts/${draftId}/regenerate`, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-threads'] })
      queryClient.invalidateQueries({ queryKey: ['thread-detail'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to regenerate draft')
    },
  })
}
