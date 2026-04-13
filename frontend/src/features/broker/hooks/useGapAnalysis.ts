import { useMutation, useQueryClient } from '@tanstack/react-query'
import { analyzeGaps } from '../api'

export function useGapAnalysis(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => analyzeGaps(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
    },
  })
}
