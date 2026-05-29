import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { uploadProjectDocuments } from '../api'
import type { DocumentZoneKind } from '../types/broker'

/**
 * Upload mutation for the two-zone Phase 145 UI.
 *
 * `kind` defaults to `'requirements'` for backward compatibility with any
 * caller that hasn't yet migrated to the two-zone surface; the backend upload
 * endpoint applies the same default when the Form field is absent.
 */
export function useDocumentUpload(
  projectId: string,
  kind: DocumentZoneKind = 'requirements',
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => uploadProjectDocuments(projectId, files, kind),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Documents uploaded successfully')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Upload failed')
    },
  })
}
