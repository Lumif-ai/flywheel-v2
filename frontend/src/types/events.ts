export type SSEEventType = 'thinking' | 'text' | 'skill_start' | 'stage' | 'result' | 'clarify' | 'error' | 'done'

export interface SSEEvent {
  type: SSEEventType
  data: Record<string, unknown>
}

export interface ThinkingEvent {
  content: string
}

export interface TextEvent {
  content: string
}

export interface SkillStartEvent {
  skill_name: string
  run_id: string
}

export interface ClarifyEvent {
  question: string
  options?: string[]
}

export interface ErrorEvent {
  message: string
}

export interface StageEvent {
  stage: string
  message?: string
}

export interface ResultEvent {
  rendered_html: string
  tokens_used?: number
  cost_estimate?: number
}

export interface DoneEvent {
  run_id: string
  status: string
  rendered_html?: string
  tokens_used?: number
  cost_estimate?: number
  duration_ms?: number
}
