import { useMutation, useQueryClient } from '@tanstack/react-query'
import { triggerAnalysis } from '../api'

export function useAnalyzeProject(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => triggerAnalysis(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      qc.invalidateQueries({ queryKey: ['broker-dashboard-stats'] })
    },
  })
}
