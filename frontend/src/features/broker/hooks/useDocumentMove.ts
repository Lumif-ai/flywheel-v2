import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { patchProjectDocument } from '../api'
import type { DocumentZoneKind } from '../types/broker'

interface MoveArgs {
  fileId: string
  documentType: DocumentZoneKind
}

/**
 * Mutation hook for Phase 145's "move to other zone" action on a misrouted doc.
 *
 * Wraps `PATCH /broker/projects/{id}/documents/{file_id}`. The backend clears
 * the prior `misrouted` flag as part of the same write so the chip disappears
 * on the next render after query invalidation.
 */
export function useDocumentMove(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ fileId, documentType }: MoveArgs) =>
      patchProjectDocument(projectId, fileId, documentType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Document moved')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Move failed')
    },
  })
}
