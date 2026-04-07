export interface PaginatedResponse<T> {
  items: T[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export interface ApiErrorResponse {
  error: string
  message: string
  code: number
}

export interface ContextFile {
  file_name: string
  entry_count: number
  last_updated: string
}

export interface ContextEntry {
  id: string
  file_name: string
  source: string
  detail: string
  confidence: string
  evidence: number
  content: string
  created_at: string
  updated_at: string
  visibility: string
  metadata?: Record<string, unknown>
}

export interface WorkItem {
  id: string
  title: string
  description: string
  status: string
  skill_name: string | null
  created_at: string
  updated_at: string
}

export interface SkillRun {
  id: string
  skill_name: string
  status: string
  input_params: Record<string, unknown>
  output_html: string | null
  events_log: unknown[]
  tokens_used: number | null
  cost_estimate: number | null
  created_at: string
  completed_at: string | null
}

export interface Skill {
  name: string
  display_name: string
  description: string
  category: string
}

export interface Tenant {
  id: string
  name: string
  slug: string
  plan: string
  member_limit: number
  features: Record<string, boolean>
}

export interface User {
  id: string
  email: string | null
  is_anonymous: boolean
}

export interface Focus {
  id: string
  name: string
  description: string | null
  settings: Record<string, unknown> | null
  created_by: string
  created_at: string
  updated_at: string
  archived_at: string | null
  member_count?: number
}
