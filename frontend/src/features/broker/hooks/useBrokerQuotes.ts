import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  extractQuote,
  fetchComparison,
  fetchProjectQuotes,
  markQuoteReceived,
  updateQuoteManual,
  draftFollowups,
} from '../api'
import type { ManualQuotePayload } from '../types/broker'
import { toast } from 'sonner'

export function useBrokerQuotes(projectId: string) {
  return useQuery({
    queryKey: ['broker', 'project-quotes', projectId],
    queryFn: () => fetchProjectQuotes(projectId),
    enabled: !!projectId,
    staleTime: 10_000,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data && Array.isArray(data) && data.some((q) => q.status === 'extracting')) {
        return 10_000
      }
      return false
    },
  })
}

export function useComparison(projectId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['broker', 'comparison', projectId],
    queryFn: () => fetchComparison(projectId),
    enabled: !!projectId && enabled,
    staleTime: 30_000,
  })
}

export function useExtractQuote(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ quoteId, force }: { quoteId: string; force?: boolean }) =>
      extractQuote(quoteId, force),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      toast.success('Quote extraction started')
    },
    onError: () => toast.error('Failed to start quote extraction'),
  })
}

export function useMarkReceived(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (quoteId: string) => markQuoteReceived(quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Quote marked as received')
    },
    onError: () => toast.error('Failed to mark quote as received'),
  })
}

export function useManualQuoteEntry(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ quoteId, payload }: { quoteId: string; payload: ManualQuotePayload }) =>
      updateQuoteManual(quoteId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      toast.success('Quote updated manually')
    },
    onError: () => toast.error('Failed to update quote'),
  })
}

export function useDraftFollowups(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => draftFollowups(projectId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['broker', 'project-quotes', projectId] })
      toast.success(`${data.followups.length} follow-up drafts created`)
    },
    onError: () => toast.error('Failed to draft follow-ups'),
  })
}
