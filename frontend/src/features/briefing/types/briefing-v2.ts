/**
 * TypeScript interfaces for the /briefing/v2 endpoint.
 * Mirrors backend Pydantic models in backend/src/flywheel/api/briefing.py (lines 163-219).
 */

export interface MeetingItem {
  id: string
  title: string | null
  time: string // ISO datetime
  attendees: Array<Record<string, unknown>> | null
  company: string | null
  prep_status: string | null // "available" | "none"
}

export interface TaskItem {
  id: string
  title: string
  due_date: string | null
  source: string // "manual" | "meeting" | "email"
  status: string
}

export interface AttentionItem {
  id: string
  type: string // "reply" | "follow_up" | "draft"
  title: string
  preview: string | null
  contact_name: string | null
  company_name: string | null
  days_overdue?: number | null
  link?: string | null
}

export interface TeamActivityGroup {
  type: string // "skill_runs" | "context_writes" | "documents"
  count: number
  items: Array<Record<string, unknown>>
}

export interface TodaySection {
  meetings: MeetingItem[]
  tasks: TaskItem[]
}

export interface AttentionSection {
  replies: AttentionItem[]
  follow_ups: AttentionItem[]
  drafts: AttentionItem[]
}

export interface BriefingV2Response {
  narrative_summary: string
  today: TodaySection
  attention_items: AttentionSection
  team_activity: TeamActivityGroup[]
  tasks_today: TaskItem[]
}
