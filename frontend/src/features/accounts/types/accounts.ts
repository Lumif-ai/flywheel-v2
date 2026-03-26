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
