export interface ContextRef {
  entry_id: string
  file_name?: string
  content_preview?: string
}

export interface Score {
  priority: number
  category: string
  reasoning: string | null
  suggested_action: string | null
  context_refs: ContextRef[]
}

export interface Message {
  id: string
  gmail_message_id: string
  sender_email: string
  sender_name: string
  subject: string
  snippet: string
  received_at: string
  is_read: boolean
  is_replied: boolean
  score: Score | null
}

export interface Draft {
  id: string
  status: 'pending' | 'sent' | 'dismissed'
  draft_body: string | null
  user_edits: string | null
}

export type PriorityTier = 'critical' | 'high' | 'medium' | 'low' | 'unscored'

export interface Thread {
  thread_id: string
  subject: string
  sender_name: string
  sender_email: string
  latest_received_at: string
  message_count: number
  max_priority: number | null
  priority_tier: PriorityTier
  has_pending_draft: boolean
  draft_id: string | null
  is_read: boolean
}

export interface ThreadListResponse {
  threads: Thread[]
  total: number
  offset: number
  limit: number
}

export interface ThreadDetailResponse {
  thread_id: string
  subject: string
  messages: Message[]
  draft: Draft | null
  max_priority: number | null
  priority_tier: PriorityTier
}

export type FlatItem =
  | { type: 'header'; tier: PriorityTier; label: string }
  | { type: 'thread'; thread: Thread }

// Daily digest types
export interface DigestThread {
  thread_id: string
  subject: string | null
  sender_email: string
  category: string | null
  priority: number | null
  message_count: number
}

export interface DigestResponse {
  date: string
  threads: DigestThread[]
  total: number
}
