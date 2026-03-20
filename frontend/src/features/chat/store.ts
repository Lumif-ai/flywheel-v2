import { create } from 'zustand'
import { api } from '@/lib/api'
import type { ChatMessage, StreamState } from './types'

const initialStreamState: StreamState = {
  status: 'idle',
  chunks: [],
  outputHtml: null,
  error: null,
}

interface ChatState {
  messages: ChatMessage[]
  streamState: StreamState
  activeRunId: string | null

  addMessage: (msg: ChatMessage) => void
  setActiveRunId: (id: string | null) => void
  setStreamStatus: (status: StreamState['status']) => void
  appendChunk: (content: string) => void
  setStreamOutput: (html: string) => void
  setStreamError: (error: string) => void
  resetStream: () => void
  sendMessage: (content: string) => Promise<void>
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  streamState: { ...initialStreamState },
  activeRunId: null,

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  setActiveRunId: (id) => set({ activeRunId: id }),

  setStreamStatus: (status) =>
    set((s) => ({ streamState: { ...s.streamState, status } })),

  appendChunk: (content) =>
    set((s) => ({
      streamState: {
        ...s.streamState,
        status: 'streaming',
        chunks: [...s.streamState.chunks, content],
      },
    })),

  setStreamOutput: (html) =>
    set((s) => {
      const messages = [...s.messages]
      const lastIdx = messages.length - 1
      if (lastIdx >= 0 && messages[lastIdx].role === 'assistant') {
        messages[lastIdx] = {
          ...messages[lastIdx],
          outputHtml: html,
          content: s.streamState.chunks.join(''),
          status: 'complete',
        }
      }
      return {
        streamState: { ...s.streamState, outputHtml: html, status: 'complete' },
        messages,
      }
    }),

  setStreamError: (error) =>
    set((s) => {
      const messages = [...s.messages]
      const lastIdx = messages.length - 1
      if (lastIdx >= 0 && messages[lastIdx].role === 'assistant') {
        messages[lastIdx] = {
          ...messages[lastIdx],
          status: 'error',
          content: error,
        }
      }
      return {
        streamState: { ...s.streamState, error, status: 'error' },
        messages,
      }
    }),

  resetStream: () => set({ streamState: { ...initialStreamState }, activeRunId: null }),

  sendMessage: async (content) => {
    const { addMessage, setActiveRunId, resetStream } = get()

    // Reset any previous stream state
    resetStream()

    // Add user message
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date(),
      status: 'complete',
    }
    addMessage(userMsg)

    try {
      const res = await api.post<{
        action: string
        run_id?: string
        stream_url?: string
        skill_name?: string
        message?: string
        candidates?: string[]
      }>('/chat', { message: content })

      if (res.action === 'execute') {
        setActiveRunId(res.run_id!)

        // Add placeholder assistant message for streaming
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          runId: res.run_id,
          skillName: res.skill_name ?? undefined,
          status: 'streaming',
        }
        addMessage(assistantMsg)
      } else if (res.action === 'clarify') {
        // Clarification -- no streaming, just display message
        const clarifyMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.message ?? 'Could you be more specific?',
          timestamp: new Date(),
          status: 'complete',
        }
        addMessage(clarifyMsg)
      } else {
        // action === "none" or unknown
        const noneMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.message ?? 'I can help with skills like research, analysis, and more.',
          timestamp: new Date(),
          status: 'complete',
        }
        addMessage(noneMsg)
      }
    } catch (err) {
      // Add error assistant message
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: err instanceof Error ? err.message : 'Failed to process message',
        timestamp: new Date(),
        status: 'error',
      }
      addMessage(errorMsg)
    }
  },
}))
