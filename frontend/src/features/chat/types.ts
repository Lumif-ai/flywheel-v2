export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  runId?: string
  outputHtml?: string
  skillName?: string
  status: 'pending' | 'streaming' | 'complete' | 'error'
}

export interface HistoryEntry {
  role: 'user' | 'assistant'
  content: string
}

export interface StreamState {
  status: 'idle' | 'thinking' | 'streaming' | 'running' | 'complete' | 'error'
  chunks: string[]
  outputHtml: string | null
  error: string | null
}
