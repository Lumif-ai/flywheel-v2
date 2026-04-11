export type RelationshipType = 'prospect' | 'customer' | 'advisor' | 'investor'

export interface RelationshipListItem {
  id: string
  name: string
  domain: string | null
  relationship_type: string[]
  entity_type: string
  stage: string
  status?: string
  ai_summary: string | null
  signal_count: number
  primary_contact_name: string | null
  last_activity_at: string | null
  created_at: string
}

export interface ContactItem {
  id: string
  name: string
  title: string | null
  email: string | null
  linkedin_url: string | null
  role: string | null
  created_at: string  // NOTE: no last_contacted_at — use created_at for "Added X ago" display
}

export interface TimelineItem {
  id: string
  source: string
  content: string
  date: string
  created_at: string
  direction: string | null  // "inbound" | "outbound" | "internal" | "bidirectional" — derived server-side
  contact_name: string | null  // extracted from content patterns server-side
}

export interface RelationshipDetailItem extends RelationshipListItem {
  ai_summary_updated_at: string | null
  contacts: ContactItem[]
  recent_timeline: TimelineItem[]
  commitments: unknown[]
  intel: Record<string, unknown>  // JSONB intelligence data returned by backend
}

export interface TypeBadge {
  type: string
  label: string
  total_signals: number
  counts: {
    reply_received: number
    followup_overdue: number
    commitment_due: number
    stale_relationship: number
  }
}

export interface SignalsResponse {
  types: TypeBadge[]
  total: number
}

export interface AskResponse {
  answer: string
  sources: Array<{ source: string; content: string; date: string }>
  insufficient_context: boolean
}
