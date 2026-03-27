import { api } from '@/lib/api'
import type { PipelineParams, PipelineResponse } from './types/pipeline'

export function fetchPipeline(params: PipelineParams): Promise<PipelineResponse> {
  // Serialize array params as comma-separated strings so backend can split them
  const serialized: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v) && v.length > 0) {
      serialized[k] = v.join(',')
    } else if (v !== undefined && v !== null && !Array.isArray(v)) {
      serialized[k] = v
    }
  }
  return api.get<PipelineResponse>('/pipeline/', { params: serialized })
}

export interface GraduatePayload {
  id: string
  types: string[]
  entity_level?: string
}

export function graduateAccount(payload: GraduatePayload): Promise<unknown> {
  return api.post(`/relationships/${payload.id}/graduate`, {
    types: payload.types,
    entity_level: payload.entity_level,
  })
}
