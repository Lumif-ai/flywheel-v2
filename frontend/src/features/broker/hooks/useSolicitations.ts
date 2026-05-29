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

/**
 * Phase 150.1 Plan 03 (Blocker-3 branch P3):
 * `draftSolicitations` warms the /broker/extract/solicitation-draft endpoint
 * per selected carrier but cannot complete Pattern 3a server-side
 * (web_tier=3). `onHandoff` fires on success with the pre-filled slash command
 * so the caller can open the ClaudeCommandModal.
 */
export function useDraftSolicitations(
  projectId: string,
  opts?: { onHandoff?: (command: string) => void },
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (carrierConfigIds: string[]) => draftSolicitations(projectId, carrierConfigIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      opts?.onHandoff?.(`/broker:draft-emails ${projectId}`)
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
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      qc.invalidateQueries({ queryKey: ['broker', 'solicitation-drafts', projectId] })
      toast.success('Solicitation email sent')
    },
    onError: () => toast.error('Failed to send solicitation email'),
  })
}

export function useEditDraft(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ draftId, payload }: { draftId: string; payload: { subject?: string; body?: string } }) =>
      editSolicitationDraft(draftId, payload),
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
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Portal submission confirmed')
    },
    onError: () => toast.error('Failed to confirm portal submission'),
  })
}
