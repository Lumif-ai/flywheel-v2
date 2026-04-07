import { useQuery } from '@tanstack/react-query'
import { fetchPipelineDetail } from '../api'
import type { PipelineDetail } from '../types/pipeline'

export function usePipelineDetail(id: string | null) {
  return useQuery<PipelineDetail>({
    queryKey: ['pipeline-detail', id],
    queryFn: () => fetchPipelineDetail(id!),
    staleTime: 60_000,
    enabled: !!id,
  })
}
