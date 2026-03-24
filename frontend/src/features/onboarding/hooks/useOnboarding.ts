import { useState, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useSSE } from '@/lib/sse'
import { getSupabase } from '@/lib/supabase'
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
  label: string
  items: string[]
  count: number
}

export interface CrawlItemMeta {
  source: 'crawler' | 'user_input'
  confidence: 'crawled' | 'verified' | 'confirmed'
  deleted?: boolean
}

export interface EditedCategory {
  items: string[]
  meta: CrawlItemMeta[]
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

export interface PriorityOption {
  id: 'grow_revenue' | 'raise_capital' | 'track_competitors'
  label: string
  subLabel: string
  capabilityCount: number
  capabilities: string[]
  focusArea: string
  firstAction: string
}

export interface OnboardingState {
  phase: OnboardingPhase
  crawlItems: CrawlItem[]
  crawlTotal: number
  crawlStatus: string | null
  parsedStreams: ParsedStream[]
  createdStreams: CreatedStream[]
  briefingHtml: string | null
  error: string | null
  loading: boolean
  sseUrl: string | null
  editedItems: Record<string, EditedCategory>
  editMode: boolean
  selectedPriorities: string[]
}

// ---------------------------------------------------------------------------
// Priority options (skills-backed)
// ---------------------------------------------------------------------------

const PRIORITY_OPTIONS: PriorityOption[] = [
  {
    id: 'grow_revenue',
    label: 'Grow revenue',
    subLabel: 'Research prospects, score leads, prep for every sales meeting',
    capabilityCount: 10,
    capabilities: ['account-research', 'account-competitive', 'account-strategy', 'gtm-company-fit-analyzer', 'gtm-leads-pipeline', 'gtm-outbound-messenger', 'gtm-web-scraper-extractor', 'gtm-dashboard', 'sales-collateral', 'demo-prep'],
    focusArea: 'Revenue',
    firstAction: 'Paste a prospect\'s website to get your first account brief',
  },
  {
    id: 'raise_capital',
    label: 'Raise capital',
    subLabel: 'Investor briefs, valuation snapshots, monthly updates',
    capabilityCount: 4,
    capabilities: ['meeting-prep', 'investor-update', 'valuation-expert', 'quick-valuation'],
    focusArea: 'Fundraise',
    firstAction: 'Who\'s your next investor meeting with?',
  },
  {
    id: 'track_competitors',
    label: 'Track competitors',
    subLabel: 'Competitive landscapes, market shifts, pricing benchmarks',
    capabilityCount: 3,
    capabilities: ['account-research', 'account-competitive', 'gtm-company-fit-analyzer'],
    focusArea: 'Market',
    firstAction: 'Name a competitor to start tracking',
  },
]

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const initialState: OnboardingState = {
  phase: 'url_input',
  crawlItems: [],
  crawlTotal: 0,
  crawlStatus: null,
  parsedStreams: [],
  createdStreams: [],
  briefingHtml: null,
  error: null,
  loading: false,
  sseUrl: null,
  editedItems: {},
  editMode: false,
  selectedPriorities: [],
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useOnboarding() {
  const [state, setState] = useState<OnboardingState>({ ...initialState })
  const stateRef = useRef(state)
  stateRef.current = state
  const queryClient = useQueryClient()

  // ---- SSE handler for crawl events ----
  const handleCrawlEvent = useCallback((event: SSEEvent) => {
    const data = event.data as Record<string, unknown>

    switch (event.type) {
      case 'stage': {
        // Progress update from backend (crawling, structuring, enriching, etc.)
        const message = (data.message as string) ?? ''
        if (message) {
          setState((s) => ({ ...s, crawlStatus: message }))
        }
        break
      }
      case 'text': {
        // Grouped discovery from backend (e.g. "Products" with list of items)
        const item: CrawlItem = {
          category: (data.category as string) ?? 'company_info',
          icon: (data.icon as string) ?? 'Building2',
          label: (data.label as string) ?? '',
          items: (data.items as string[]) ?? [],
          count: (data.count as number) ?? stateRef.current.crawlItems.length + 1,
        }
        setState((s) => ({
          ...s,
          crawlItems: [...s.crawlItems, item],
          crawlTotal: s.crawlTotal + item.items.length,
          crawlStatus: null,
        }))
        break
      }
      case 'done': {
        const totalItems = (data.total_items as number) ?? stateRef.current.crawlItems.length
        // Auto-enter edit mode: copy crawlItems into editedItems
        const edited: Record<string, EditedCategory> = {}
        const currentItems = [...stateRef.current.crawlItems]
        // Include any items from this last event batch
        for (const group of currentItems) {
          edited[group.category] = {
            items: [...group.items],
            meta: group.items.map(() => ({ source: 'crawler' as const, confidence: 'crawled' as const })),
          }
        }
        setState((s) => {
          // Re-derive from latest state to capture all items
          const freshEdited: Record<string, EditedCategory> = {}
          for (const group of s.crawlItems) {
            freshEdited[group.category] = {
              items: [...group.items],
              meta: group.items.map(() => ({ source: 'crawler' as const, confidence: 'crawled' as const })),
            }
          }
          return {
            ...s,
            phase: 'crawl_complete',
            crawlTotal: totalItems,
            crawlStatus: null,
            sseUrl: null,
            editMode: true,
            editedItems: freshEdited,
          }
        })
        break
      }
      case 'error':
        setState((s) => ({
          ...s,
          error: (data.message as string) ?? 'Crawl failed',
          phase: 'url_input',
          crawlStatus: null,
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
      const supabase = await getSupabase()

      if (supabase) {
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
        sseUrl: `/api/v1/onboarding/crawl/${runId}/stream`,
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
      // Invalidate sidebar streams cache so new streams appear immediately
      queryClient.invalidateQueries({ queryKey: ['streams'] })
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

  const goToBriefing = useCallback((briefingHtml?: string) => {
    setState((s) => ({
      ...s,
      phase: 'first_briefing',
      briefingHtml: briefingHtml || s.briefingHtml,
    }))
  }, [])

  const retry = useCallback(() => {
    setState({ ...initialState })
  }, [])

  // ---- Edit mode actions (MomentDiscover) ----

  const removeItem = useCallback((category: string, itemIndex: number) => {
    setState((s) => {
      const edited = { ...s.editedItems }
      if (!edited[category]) return s
      const cat = { ...edited[category], meta: [...edited[category].meta] }
      cat.meta[itemIndex] = { ...cat.meta[itemIndex], deleted: true }
      edited[category] = cat
      return { ...s, editedItems: edited }
    })
  }, [])

  const addItem = useCallback((category: string, text: string) => {
    setState((s) => {
      const edited = { ...s.editedItems }
      const cat = edited[category]
        ? { items: [...edited[category].items], meta: [...edited[category].meta] }
        : { items: [], meta: [] }
      cat.items.push(text)
      cat.meta.push({ source: 'user_input', confidence: 'verified' })
      edited[category] = cat
      return { ...s, editedItems: edited }
    })
  }, [])

  const editItem = useCallback((category: string, itemIndex: number, newText: string) => {
    setState((s) => {
      const edited = { ...s.editedItems }
      if (!edited[category]) return s
      const cat = { items: [...edited[category].items], meta: [...edited[category].meta] }
      cat.items[itemIndex] = newText
      cat.meta[itemIndex] = { ...cat.meta[itemIndex], confidence: 'verified' }
      edited[category] = cat
      return { ...s, editedItems: edited }
    })
  }, [])

  const confirmEdits = useCallback(() => {
    setState((s) => {
      // Write edited items back to crawlItems
      const updatedCrawlItems = s.crawlItems.map((group) => {
        const edited = s.editedItems[group.category]
        if (!edited) return group
        // Filter out deleted items
        const finalItems: string[] = []
        for (let i = 0; i < edited.items.length; i++) {
          if (!edited.meta[i]?.deleted) {
            finalItems.push(edited.items[i])
          }
        }
        return { ...group, items: finalItems, count: finalItems.length }
      })
      return {
        ...s,
        crawlItems: updatedCrawlItems,
        crawlTotal: updatedCrawlItems.reduce((sum, g) => sum + g.items.length, 0),
        editMode: false,
      }
    })
  }, [])

  // ---- Priority selection actions (MomentAlign) ----

  const togglePriority = useCallback((id: string) => {
    setState((s) => {
      const selected = s.selectedPriorities.includes(id)
        ? s.selectedPriorities.filter((p) => p !== id)
        : [...s.selectedPriorities, id]
      return { ...s, selectedPriorities: selected }
    })
  }, [])

  const confirmPriorities = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const selected = stateRef.current.selectedPriorities
      const options = PRIORITY_OPTIONS.filter((o) => selected.includes(o.id))
      const streams = options.map((o) => ({
        name: o.focusArea,
        description: o.subLabel,
        entity_seeds: [] as string[],
      }))
      const res = await api.post<{ created: CreatedStream[] }>('/onboarding/create-streams', { streams })
      queryClient.invalidateQueries({ queryKey: ['streams'] })
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
        error: err instanceof Error ? err.message : 'Failed to create focus areas',
      }))
    }
  }, [queryClient])

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
    // Edit mode actions
    removeItem,
    addItem,
    editItem,
    confirmEdits,
    // Priority actions
    togglePriority,
    confirmPriorities,
    priorityOptions: PRIORITY_OPTIONS,
  }
}
