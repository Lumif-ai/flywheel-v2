export interface PipelineListItem {
  id: string
  name: string
  domain: string | null
  entity_type: 'company' | 'person'
  stage: string
  fit_score: number | null
  fit_tier: string | null
  relationship_type: string[]
  source: string
  channels: string[]
  ai_summary: string | null
  next_action_date: string | null
  next_action_note: string | null
  last_activity_at: string | null
  created_at: string | null
  stale_notified_at: string | null
  retired_at: string | null
  contact_count: number
  primary_contact: { name: string; email: string | null; title: string | null } | null
  outreach_summary: { [status: string]: number } | null
}

export interface PipelineResponse {
  items: PipelineListItem[]
  total: number
  offset: number
  limit: number
}

export interface PipelineDetailRow {
  _isDetailRow: true
  _parentId: string
  _parentName: string
  id: string
}

export type PipelineGridRow = (PipelineListItem & { _isDetailRow?: false }) | PipelineDetailRow

export type ViewTab = 'all' | 'needs_action' | 'replied' | 'stale'

export interface PipelineParams {
  offset?: number
  limit?: number
  search?: string
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  stage?: string[]
  fit_tier?: string[]
  relationship_type?: string[]
  source?: string
  view?: ViewTab
  include_retired?: boolean
}

export type EditableField = 'stage' | 'fit_tier' | 'next_action_date'

/* ------------------------------------------------------------------ */
/* Detail / Side Panel types                                           */
/* ------------------------------------------------------------------ */

export interface PipelineDetail {
  id: string
  name: string
  domain: string | null
  entity_type: 'company' | 'person'
  stage: string
  fit_score: number | null
  fit_tier: string | null
  fit_rationale: string | null
  relationship_type: string[]
  source: string
  channels: string[]
  last_activity_at: string | null
  created_at: string | null
  stale_notified_at: string | null
  retired_at: string | null
  contact_count: number
  primary_contact: { name: string; email: string | null; title: string | null } | null
  intel: PipelineIntel
  ai_summary: string | null
  contacts: PipelineContact[]
  recent_activities: PipelineActivity[]
  sources: PipelineSource[]
}

/** Typed intel sub-object -- optional fields since intel may be partially populated */
export interface PipelineIntel {
  industry?: string
  description?: string
  what_they_do?: string
  headquarters?: string
  employees?: string
  funding?: string
  tagline?: string
  key_insights?: KeyInsight[]
  outreach_sequence?: OutreachStep[]
  [key: string]: unknown // allow other dynamic fields
}

export interface PipelineContact {
  id: string
  name: string
  email: string | null
  title: string | null
  role: string | null
  linkedin_url: string | null
  phone: string | null
  notes: string | null
  is_primary: boolean
  created_at: string | null
}

export interface PipelineActivity {
  id: string
  type: string
  channel: string | null
  direction: string | null
  status: string
  subject: string | null
  body_preview: string | null
  metadata: Record<string, unknown>
  contact_id: string | null
  occurred_at: string | null
  created_at: string | null
}

export interface TimelineItem {
  id: string
  source_type: 'activity' | 'meeting' | 'context'
  date: string
  title: string
  summary: string | null
  type: string | null
  channel: string | null
  direction: string | null
  status: string | null
  metadata: Record<string, unknown> | null
}

export interface TimelineResponse {
  items: TimelineItem[]
  total: number
}

export interface PipelineSource {
  id: string
  source_type: string
  source_ref_id: string | null
  created_at: string | null
}

export interface PipelineTaskItem {
  id: string
  title: string
  description: string | null
  task_type: string
  status: string
  priority: string
  due_date: string | null
  pipeline_entry_id: string | null
  created_at: string | null
}

/** Key Insight structure from company intel */
export interface KeyInsight {
  text: string
  tag: 'Signal' | 'Pain' | 'Commitment' | 'Context'
}

/** Outreach Sequence step from company intel */
export interface OutreachStep {
  step: number
  channel: string
  subject: string
  body: string
  status: 'draft' | 'sent' | 'replied'
}

/* ------------------------------------------------------------------ */
/* Saved Views                                                         */
/* ------------------------------------------------------------------ */

export interface SavedView {
  id: string
  name: string
  filters: {
    stage?: string[]
    fitTier?: string[]
    relationshipType?: string[]
    source?: string
    view?: ViewTab
    search?: string
  }
  sort?: { colId: string; sort: 'asc' | 'desc' } | null
  columns?: unknown[] | null
  isDefault: boolean
  position: number
  createdAt: string
  updatedAt: string
}

/**
 * @deprecated Use PipelineListItem instead. Kept for backward compatibility
 * with existing grid components until they are rebuilt in Plan 02+.
 */
export type PipelineItem = PipelineListItem

/* ------------------------------------------------------------------ */
/* Contact Grid types (Phase 092)                                      */
/* ------------------------------------------------------------------ */

export interface ContactListItem {
  id: string
  name: string
  email: string | null
  title: string | null
  linkedin_url: string | null
  phone: string | null
  is_primary: boolean
  company_name: string
  company_domain: string | null
  pipeline_entry_id: string
  channels: string[]
  source: string | null
  campaign: string | null
  latest_activity: {
    id: string
    channel: string | null
    variant: string | null
    variant_theme: string | null
    step_number: number | null
    status: string | null
    subject: string | null
    occurred_at: string | null
  } | null
  next_step: string
  created_at: string | null
}

export interface ContactListResponse {
  items: ContactListItem[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export interface ContactParams {
  offset?: number
  limit?: number
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  company?: string
  status?: string
  channel?: string
  variant?: string
  step_number?: number
  include_retired?: boolean
  enabled?: boolean  // controls TanStack Query enabled flag
}

export type GridMode = 'contacts' | 'companies'
