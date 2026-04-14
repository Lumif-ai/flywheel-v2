import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { approveProject } from '../api'

export function useApproveProject(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => approveProject(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      toast.success('Project approved')
    },
    onError: (error: unknown) => {
      const status = (error as { status?: number })?.status
      if (status === 409) {
        toast.info('Project already approved')
      } else {
        toast.error('Failed to approve project')
      }
    },
  })
}
