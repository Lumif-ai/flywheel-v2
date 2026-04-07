import { api } from '@/lib/api'
import type { Lead, LeadsResponse, PipelineFunnel, LeadParams } from './types/lead'

export function fetchLeads(params: LeadParams): Promise<LeadsResponse> {
  const clean: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) clean[k] = v
  }
  return api.get<LeadsResponse>('/leads/', { params: clean })
}

export function fetchLeadsPipeline(): Promise<PipelineFunnel> {
  return api.get<PipelineFunnel>('/leads/pipeline')
}

export function fetchLeadDetail(id: string): Promise<Lead> {
  return api.get<Lead>(`/leads/${id}`)
}
