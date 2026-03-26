// Types matching backend API schemas for accounts endpoints

export type AccountStatus = 'prospect' | 'engaged' | 'customer' | 'churned' | 'disqualified'

export type FitTier = 'excellent' | 'good' | 'fair' | 'poor'

export interface AccountListItem {
  id: string
  name: string
  domain: string | null
  status: AccountStatus
  fit_score: number | null
  fit_tier: FitTier | null
  contact_count: number
  last_interaction_at: string | null
  next_action_due: string | null
  next_action_type: string | null
  source: string
}

export interface AccountListResponse {
  items: AccountListItem[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export interface AccountListParams {
  offset?: number
  limit?: number
  status?: string
  search?: string
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
}

export interface ContactResponse {
  id: string
  name: string
  email: string | null
  title: string | null
  role_in_deal: string | null
  linkedin_url: string | null
  notes: string | null
  source: string
  created_at: string | null
}

export interface TimelineItem {
  id: string
  type: 'outreach' | 'context'
  date: string | null
  title: string
  summary: string | null
  status: string | null
  channel: string | null
  direction: string | null
  source: string | null
  confidence: string | null
}

export interface TimelineResponse {
  items: TimelineItem[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export interface AccountDetail extends AccountListItem {
  intel: Record<string, unknown>
  contacts: ContactResponse[]
  recent_timeline: TimelineItem[]
}
