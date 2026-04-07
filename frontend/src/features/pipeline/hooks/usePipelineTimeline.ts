import { useQuery } from '@tanstack/react-query'
import { fetchPipelineTimeline } from '../api'
import type { TimelineResponse } from '../types/pipeline'

export function usePipelineTimeline(id: string | null) {
  return useQuery<TimelineResponse>({
    queryKey: ['pipeline-timeline', id],
    queryFn: () => fetchPipelineTimeline(id!),
    staleTime: 30_000,
    enabled: !!id,
  })
}
