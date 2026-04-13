import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  draftSolicitations,
  editSolicitationDraft,
  approveSendSolicitation,
  confirmPortalSubmission,
  fetchProjectQuotes,
} from '../api'
import { toast } from 'sonner'

export function useProjectQuotes(projectId: string) {
  return useQuery({
    queryKey: ['broker', 'project-quotes', projectId],
    queryFn: () => fetchProjectQuotes(projectId),
    enabled: !!projectId,
    staleTime: 15_000,
  })
}

export function useDraftSolicitations(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (carrierConfigIds: string[]) => draftSolicitations(projectId, carrierConfigIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      qc.invalidateQueries({ queryKey: ['broker', 'project', projectId] })
      toast.success('Solicitation drafts created')
    },
    onError: () => toast.error('Failed to create solicitation drafts'),
  })
}

export function useApproveSend(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (quoteId: string) => approveSendSolicitation(quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      qc.invalidateQueries({ queryKey: ['broker', 'project', projectId] })
      toast.success('Solicitation email sent')
    },
    onError: () => toast.error('Failed to send solicitation email'),
  })
}

export function useEditDraft(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ quoteId, payload }: { quoteId: string; payload: { draft_subject?: string; draft_body?: string } }) =>
      editSolicitationDraft(quoteId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
    },
    onError: () => toast.error('Failed to update draft'),
  })
}

export function useConfirmPortal(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (quoteId: string) => confirmPortalSubmission(quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      qc.invalidateQueries({ queryKey: ['broker', 'project', projectId] })
      toast.success('Portal submission confirmed')
    },
    onError: () => toast.error('Failed to confirm portal submission'),
  })
}
