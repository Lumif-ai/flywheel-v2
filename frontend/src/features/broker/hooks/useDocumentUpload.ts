import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { uploadProjectDocuments } from '../api'

export function useDocumentUpload(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => uploadProjectDocuments(projectId, files),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Documents uploaded successfully')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Upload failed')
    },
  })
}
