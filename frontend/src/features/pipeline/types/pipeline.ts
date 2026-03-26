export interface PipelineItem {
  id: string
  name: string
  domain: string | null
  fit_score: number | null
  fit_tier: string | null
  status: string
  last_interaction_at: string | null
  outreach_count: number
  last_outreach_status: string | null
  days_since_last_outreach: number | null
  created_at: string
}

export interface PipelineResponse {
  items: PipelineItem[]
  total: number
  offset: number
  limit: number
}

export interface PipelineParams {
  offset?: number
  limit?: number
  fit_tier?: string
  outreach_status?: string
}
