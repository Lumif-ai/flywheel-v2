import { useQuery } from '@tanstack/react-query'
import { fetchPipeline } from '../api'
import type { PipelineParams } from '../types/pipeline'

export function usePipeline(params: PipelineParams) {
  return useQuery({
    queryKey: ['pipeline', params],
    queryFn: () => fetchPipeline(params),
    placeholderData: (prev) => prev,
  })
}
