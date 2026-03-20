export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  runId?: string
  outputHtml?: string
  status: 'pending' | 'streaming' | 'complete' | 'error'
}

export interface StreamState {
  status: 'idle' | 'thinking' | 'streaming' | 'running' | 'complete' | 'error'
  chunks: string[]
  outputHtml: string | null
  error: string | null
}
