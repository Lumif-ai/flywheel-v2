import { useQuery } from '@tanstack/react-query'
import { fetchPipelineTasks } from '../api'
import type { PipelineTaskItem } from '../types/pipeline'

export function usePipelineTasks(pipelineEntryId: string | null) {
  return useQuery<PipelineTaskItem[]>({
    queryKey: ['pipeline-tasks', pipelineEntryId],
    queryFn: () => fetchPipelineTasks(pipelineEntryId!),
    staleTime: 60_000,
    enabled: !!pipelineEntryId,
  })
}
