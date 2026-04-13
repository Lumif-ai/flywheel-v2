import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ProjectCoverage } from '../types/broker'

export function useCoverageMutation(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ coverageId, updates }: { coverageId: string; updates: Partial<ProjectCoverage> }) =>
      api.patch<ProjectCoverage>(`/broker/coverages/${coverageId}`, updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
    },
  })
}
