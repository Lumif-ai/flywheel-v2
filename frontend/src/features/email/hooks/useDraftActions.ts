import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

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
