export type SSEEventType = 'thinking' | 'text' | 'skill_start' | 'clarify' | 'error' | 'done'

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

export interface DoneEvent {
  run_id: string
  output_html?: string
}
