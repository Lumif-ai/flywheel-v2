import { useState, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import { useSSE } from '@/lib/sse'
import { useAuthStore } from '@/stores/auth'
import type { SSEEvent } from '@/types/events'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type OnboardingPhase =
  | 'url_input'
  | 'crawling'
  | 'crawl_complete'
  | 'stream_input'
  | 'stream_confirm'
  | 'meeting_notes'
  | 'first_briefing'

export interface CrawlItem {
  category: string
  icon: string
  content: string
  count: number
}

export interface ParsedStream {
  name: string
  description: string
  entity_seeds: string[]
  editing?: boolean
}

export interface CreatedStream {
  id: string
  name: string
  density_score: number
}

export interface OnboardingState {
  phase: OnboardingPhase
  crawlItems: CrawlItem[]
  crawlTotal: number
  parsedStreams: ParsedStream[]
  createdStreams: CreatedStream[]
  error: string | null
  loading: boolean
  sseUrl: string | null
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const initialState: OnboardingState = {
  phase: 'url_input',
  crawlItems: [],
  crawlTotal: 0,
  parsedStreams: [],
  createdStreams: [],
  error: null,
  loading: false,
  sseUrl: null,
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useOnboarding() {
  const [state, setState] = useState<OnboardingState>({ ...initialState })
  const stateRef = useRef(state)
  stateRef.current = state

  // ---- SSE handler for crawl events ----
  const handleCrawlEvent = useCallback((event: SSEEvent) => {
    const data = event.data as Record<string, unknown>

    switch (event.type) {
      case 'text': {
        // crawl_item event from backend (mapped through SSE as 'text' type)
        const item: CrawlItem = {
          category: (data.category as string) ?? 'company_info',
          icon: (data.icon as string) ?? 'Building2',
          content: (data.content as string) ?? '',
          count: (data.count as number) ?? stateRef.current.crawlItems.length + 1,
        }
        setState((s) => ({
          ...s,
          crawlItems: [...s.crawlItems, item],
          crawlTotal: item.count,
        }))
        break
      }
      case 'done': {
        const totalItems = (data.total_items as number) ?? stateRef.current.crawlItems.length
        setState((s) => ({
          ...s,
          phase: 'crawl_complete',
          crawlTotal: totalItems,
          sseUrl: null,
        }))
        break
      }
      case 'error':
        setState((s) => ({
          ...s,
          error: (data.message as string) ?? 'Crawl failed',
          phase: 'url_input',
          sseUrl: null,
        }))
        break
    }
  }, [])

  // Connect SSE when crawling
  useSSE(state.sseUrl, handleCrawlEvent)

  // ---- Anonymous auth guard ----
  const ensureSession = useCallback(async () => {
    const { token } = useAuthStore.getState()
    if (token) return // session already exists

    try {
      const supabaseUrl = (import.meta as any).env?.VITE_SUPABASE_URL
      const supabaseKey = (import.meta as any).env?.VITE_SUPABASE_ANON_KEY

      if (supabaseUrl && supabaseKey) {
        const { createClient } = await import('@supabase/supabase-js')
        const supabase = createClient(supabaseUrl, supabaseKey)
        const { data, error } = await supabase.auth.signInAnonymously()
        if (error) throw error
        if (data.session?.access_token) {
          useAuthStore.getState().setToken(data.session.access_token)
          useAuthStore.getState().setUser({
            id: data.user?.id ?? '',
            email: null,
            is_anonymous: true,
          })
        }
      }
      // If Supabase not configured, proceed without auth (local dev)
    } catch (err) {
      console.warn('Anonymous auth failed, proceeding without:', err)
    }
  }, [])

  // ---- Actions ----

  const startCrawl = useCallback(async (url: string) => {
    setState((s) => ({
      ...s,
      phase: 'crawling',
      crawlItems: [],
      crawlTotal: 0,
      error: null,
    }))

    try {
      // Ensure anonymous session before any API call
      await ensureSession()

      const res = await api.post<{ run_id: string }>('/onboarding/crawl', { url })
      const runId = res.run_id
      setState((s) => ({
        ...s,
        sseUrl: `/api/v1/skills/runs/${runId}/stream`,
      }))
    } catch (err) {
      setState((s) => ({
        ...s,
        phase: 'url_input',
        error: err instanceof Error ? err.message : 'Failed to start crawl',
      }))
    }
  }, [ensureSession])

  const proceedToStreams = useCallback(() => {
    setState((s) => ({ ...s, phase: 'stream_input' }))
  }, [])

  const parseStreams = useCallback(async (input: string) => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const res = await api.post<{ streams: ParsedStream[] }>('/onboarding/parse-streams', { input })
      setState((s) => ({
        ...s,
        parsedStreams: res.streams,
        phase: 'stream_confirm',
        loading: false,
      }))
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to parse streams',
      }))
    }
  }, [])

  const updateStream = useCallback((index: number, updates: Partial<ParsedStream>) => {
    setState((s) => ({
      ...s,
      parsedStreams: s.parsedStreams.map((stream, i) =>
        i === index ? { ...stream, ...updates } : stream
      ),
    }))
  }, [])

  const removeStream = useCallback((index: number) => {
    setState((s) => ({
      ...s,
      parsedStreams: s.parsedStreams.filter((_, i) => i !== index),
    }))
  }, [])

  const addStream = useCallback((name: string) => {
    setState((s) => ({
      ...s,
      parsedStreams: [
        ...s.parsedStreams,
        { name, description: '', entity_seeds: [] },
      ],
    }))
  }, [])

  const confirmStreams = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const res = await api.post<{ created: CreatedStream[] }>('/onboarding/create-streams', {
        streams: stateRef.current.parsedStreams.map((s) => ({
          name: s.name,
          description: s.description,
          entity_seeds: s.entity_seeds,
        })),
      })
      setState((s) => ({
        ...s,
        createdStreams: res.created,
        phase: 'meeting_notes',
        loading: false,
      }))
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to create streams',
      }))
    }
  }, [])

  const skipToMeetings = useCallback(() => {
    setState((s) => ({ ...s, phase: 'meeting_notes' }))
  }, [])

  const skipToBriefing = useCallback(() => {
    setState((s) => ({ ...s, phase: 'first_briefing' }))
  }, [])

  const goToBriefing = useCallback(() => {
    // Navigation handled by the page component
    setState((s) => ({ ...s, phase: 'first_briefing' }))
  }, [])

  const retry = useCallback(() => {
    setState({ ...initialState })
  }, [])

  return {
    ...state,
    startCrawl,
    proceedToStreams,
    parseStreams,
    updateStream,
    removeStream,
    addStream,
    confirmStreams,
    skipToMeetings,
    skipToBriefing,
    goToBriefing,
    retry,
  }
}
