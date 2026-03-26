import { api } from '@/lib/api'
import type { PipelineParams, PipelineResponse } from './types/pipeline'

export function fetchPipeline(params: PipelineParams): Promise<PipelineResponse> {
  return api.get<PipelineResponse>('/pipeline/', { params: params as Record<string, unknown> })
}

export function graduateAccount(accountId: string): Promise<void> {
  return api.post('/accounts/' + accountId + '/graduate')
}
