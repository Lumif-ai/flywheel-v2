export type BrokerProjectStatus =
  | 'new_request'
  | 'analyzing'
  | 'analysis_failed'
  | 'gaps_identified'
  | 'soliciting'
  | 'quotes_partial'
  | 'quotes_complete'
  | 'recommended'
  | 'delivered'
  | 'bound'
  | 'cancelled'

export type AnalysisStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface BrokerProject {
  id: string
  tenant_id: string
  name: string
  project_type: string
  status: BrokerProjectStatus
  analysis_status: AnalysisStatus
  contract_value: number | null
  currency: string
  language: string | null
  source: 'manual' | 'email'
  source_ref: string | null
  notes: string | null
  recommendation_subject: string | null
  recommendation_body: string | null
  recommendation_status: 'pending' | 'sent' | null
  recommendation_sent_at: string | null
  recommendation_recipient: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCoverage {
  id: string
  broker_project_id: string
  coverage_type: string
  description: string | null
  category: string
  gap_status: string
  required_limit: number | null
  current_limit: number | null
  confidence: string
  is_manual_override: boolean
  source: string
  language: string | null
}

export interface BrokerActivity {
  id: string
  broker_project_id: string
  activity_type: string
  actor_type: string | null
  description: string | null
  metadata_: Record<string, unknown> | null
  occurred_at: string
}

export interface BrokerProjectDetail extends BrokerProject {
  coverages: ProjectCoverage[]
  activities: BrokerActivity[]
}

export interface DashboardStats {
  total_projects: number
  projects_by_status: Record<string, number>
  projects_needing_action: number
  recent_projects: BrokerProject[]
}

export interface BrokerProjectListResponse {
  items: BrokerProject[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export interface GateCounts {
  review: { count: number; oldest_project_id: string | null }
  approve: { count: number; oldest_project_id: string | null }
  export: { count: number; oldest_project_id: string | null }
}

export interface DashboardTask {
  type: 'review' | 'approve' | 'export' | 'followup'
  priority: number
  project_id: string
  project_name: string
  created_at: string | null
  message: string
  carrier_name?: string
  days_overdue?: number
}

export interface DashboardTasksResponse {
  tasks: DashboardTask[]
  total: number
}

export interface CreateProjectPayload {
  name: string
  project_type?: string
  notes?: string
}

export interface CarrierConfig {
  id: string
  tenant_id: string
  carrier_name: string
  carrier_type: string
  submission_method: string
  is_active: boolean
  portal_url: string | null
  email_address: string | null
  coverage_types: string[]
  regions: string[]
  min_project_value: number | null
  max_project_value: number | null
  avg_response_days: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface GapAnalysisResponse {
  summary: { total: number; covered: number; insufficient: number; missing: number; unknown: number }
  coverages: ProjectCoverage[]
}

export interface CarrierMatch {
  carrier_config_id: string
  carrier_name: string
  carrier_type: string
  submission_method: string
  email_address: string | null
  portal_url: string | null
  matched_coverages: string[]
  unmatched_coverages: string[]
  match_score: number
  avg_response_days: number | null
}

export interface CarrierMatchResponse {
  matches: CarrierMatch[]
  project_coverage_count: number
}

export interface CreateCarrierPayload {
  carrier_name: string
  carrier_type: string
  submission_method: string
  portal_url?: string | null
  email_address?: string | null
  coverage_types?: string[]
  regions?: string[]
  min_project_value?: number | null
  max_project_value?: number | null
  avg_response_days?: number | null
  notes?: string | null
}

export interface UpdateCarrierPayload {
  carrier_name?: string
  carrier_type?: string
  submission_method?: string
  portal_url?: string | null
  email_address?: string | null
  coverage_types?: string[]
  regions?: string[]
  min_project_value?: number | null
  max_project_value?: number | null
  avg_response_days?: number | null
  notes?: string | null
  is_active?: boolean
}

export interface SolicitationDocument {
  file_id: string
  document_type: string
  display_name: string
  included: boolean
}

export interface CarrierQuote {
  id: string
  broker_project_id: string
  carrier_name: string
  carrier_config_id: string | null
  carrier_type: string
  premium: number | null
  deductible: number | null
  limit_amount: number | null
  coinsurance: number | null
  term_months: number | null
  validity_date: string | null
  exclusions: string[]
  conditions: string[]
  endorsements: string[]
  is_best_price: boolean
  is_best_coverage: boolean
  is_recommended: boolean
  has_critical_exclusion: boolean
  critical_exclusion_detail: string | null
  status: string // "pending" | "solicited" | "received" | "extracting" | "extracted" | "selected" | "rejected"
  draft_subject: string | null
  draft_body: string | null
  draft_status: string | null // null | "pending" | "sent" | "review" | "confirmed"
  solicited_at: string | null
  received_at: string | null
  confidence: string | null
  source: string
  is_manual_override: boolean
  coverage_id: string | null
  metadata_: Record<string, unknown> | null
  documents: SolicitationDocument[]
}

export interface ComparisonQuoteCell {
  quote_id: string
  carrier_name: string
  carrier_config_id: string | null
  premium: number | null
  deductible: number | null
  limit_amount: number | null
  coinsurance: number | null
  is_best_price: boolean
  is_best_coverage: boolean
  is_recommended: boolean
  has_critical_exclusion: boolean
  critical_exclusion_detail: string | null
  exclusions: string[]
  confidence: string
}

export interface ComparisonCoverage {
  coverage_id: string
  coverage_type: string
  category: string
  required_limit: number | null
  quotes: ComparisonQuoteCell[]
}

export interface ComparisonMatrix {
  coverages: ComparisonCoverage[]
  partial: boolean
  total_carriers: number
  total_coverages: number
  currency_mismatch: boolean
}

export interface FollowupResponse {
  followups: CarrierQuote[]
  not_due: Array<{ quote_id: string; carrier_name: string; days_remaining: number }>
  skipped: Array<{ carrier: string; reason: string }>
}

export interface ManualQuotePayload {
  premium?: number | null
  deductible?: number | null
  limit_amount?: number | null
  coinsurance?: number | null
  term_months?: number | null
  validity_date?: string | null
  exclusions?: string[]
  conditions?: string[]
  endorsements?: string[]
  coverage_id?: string | null
  confidence?: string
}

export interface RecommendationDraftResponse {
  subject: string
  body_html: string
  recipient: string
}

export interface DraftSolicitationsResponse {
  drafts: CarrierQuote[]
  portal_submissions: Array<{
    quote_id: string
    carrier_name: string
    carrier_config_id: string
    portal_url: string
    documents: SolicitationDocument[]
  }>
  skipped: Array<{ carrier_config_id: string; carrier_name: string; carrier: string; reason: string }>
}
