// ---------------------------------------------------------------------------
// Meetings feature types — matches backend GET /meetings/ + GET /meetings/{id}
// ---------------------------------------------------------------------------

export interface Attendee {
  email: string | null
  name: string | null
  is_external: boolean
}

export interface MeetingSummary {
  tldr: string | null
  key_decisions: string[]
  action_items: Array<{ item: string; owner?: string; due?: string }>
  pain_points: string[]
  attendee_roles: Record<string, string>
  meeting_type: string | null
}

export type ProcessingStatus = 'pending' | 'processing' | 'complete' | 'failed' | 'skipped' | 'scheduled' | 'recorded' | 'cancelled'

export interface MeetingListItem {
  id: string
  title: string | null
  meeting_date: string | null        // ISO 8601
  duration_mins: number | null
  attendees: Attendee[] | null
  meeting_type: string | null        // 'discovery' | 'prospect' | 'advisor' | etc.
  processing_status: ProcessingStatus
  provider: string                   // "google-calendar" or "granola"
  location: string | null            // meeting location from calendar
  calendar_event_id: string | null   // present for calendar-sourced meetings
  account_id: string | null
  summary: MeetingSummary | null     // JSONB: {tldr, key_decisions, action_items, pain_points, attendee_roles, meeting_type}
  created_at: string
}

// GET /meetings/{id} adds owner-only fields
export interface MeetingDetail extends MeetingListItem {
  skill_run_id: string | null
  processed_at: string | null
  updated_at: string
  transcript_url?: string | null     // owner-only (absent for non-owners)
  ai_summary?: string | null         // owner-only (absent for non-owners)
}

export interface PrepResult {
  run_id: string
  stream_url: string
}

export interface SyncResult {
  synced: number
  skipped: number
  already_seen: number
  total_from_provider: number
}
