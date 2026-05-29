import { useState, useCallback, useRef } from 'react'
import { api, apiUrl } from '@/lib/api'
import { useSSE } from '@/lib/sse'
import type { SSEEvent } from '@/types/events'

export type CrawlPhase = 'idle' | 'crawling' | 'profile' | 'first_run' | 'signup'

export interface CrawlEvent {
  type: string
  content: string
  timestamp: Date
}

export interface CompanyData {
  name: string
  description: string
  industry: string
  url: string
  details: Record<string, string>
}

interface CrawlState {
  phase: CrawlPhase
  crawlEvents: CrawlEvent[]
  companyData: CompanyData | null
  error: string | null
  runId: string | null
  skillRunId: string | null
}

const initialState: CrawlState = {
  phase: 'idle',
  crawlEvents: [],
  companyData: null,
  error: null,
  runId: null,
  skillRunId: null,
}

export function useCrawl() {
  const [state, setState] = useState<CrawlState>({ ...initialState })
  const stateRef = useRef(state)
  stateRef.current = state

  const handleCrawlEvent = useCallback((event: SSEEvent) => {
    switch (event.type) {
      case 'text':
        setState((s) => ({
          ...s,
          crawlEvents: [
            ...s.crawlEvents,
            {
              type: 'text',
              content: event.data.content as string,
              timestamp: new Date(),
            },
          ],
        }))
        break
      case 'thinking':
        setState((s) => ({
          ...s,
          crawlEvents: [
            ...s.crawlEvents,
            {
              type: 'thinking',
              content: 'Analyzing content...',
              timestamp: new Date(),
            },
          ],
        }))
        break
      case 'done': {
        // Parse the output HTML to extract company data
        const outputHtml = (event.data.output_html as string) ?? ''
        const companyData = parseCompanyData(outputHtml, stateRef.current.companyData?.url ?? '')
        setState((s) => ({
          ...s,
          phase: 'profile',
          companyData,
        }))
        break
      }
      case 'error':
        setState((s) => ({
          ...s,
          error: (event.data.message as string) ?? 'Crawl failed',
          phase: 'idle',
        }))
        break
    }
  }, [])

  // Connect SSE when crawling
  useSSE(
    state.phase === 'crawling' && state.runId
      ? apiUrl(`/api/v1/skills/runs/${state.runId}/stream`)
      : null,
    handleCrawlEvent,
  )

  // Handle first skill run SSE events
  const handleSkillEvent = useCallback((event: SSEEvent) => {
    if (event.type === 'done') {
      setState((s) => ({ ...s, phase: 'signup' }))
    } else if (event.type === 'error') {
      setState((s) => ({
        ...s,
        error: (event.data.message as string) ?? 'Skill run failed',
        phase: 'profile',
      }))
    }
  }, [])

  useSSE(
    state.phase === 'first_run' && state.skillRunId
      ? apiUrl(`/api/v1/skills/runs/${state.skillRunId}/stream`)
      : null,
    handleSkillEvent,
  )

  const startCrawl = useCallback(async (url: string) => {
    setState((s) => ({
      ...s,
      phase: 'crawling',
      crawlEvents: [
        { type: 'status', content: 'Fetching website...', timestamp: new Date() },
      ],
      error: null,
      companyData: { name: '', description: '', industry: '', url, details: {} },
    }))

    try {
      const res = await api.post<{ run_id: string }>('/onboarding/crawl', { url })
      setState((s) => ({ ...s, runId: res.run_id }))
    } catch (err) {
      setState((s) => ({
        ...s,
        phase: 'idle',
        error: err instanceof Error ? err.message : 'Failed to start crawl',
      }))
    }
  }, [])

  const runFirstSkill = useCallback(async () => {
    setState((s) => ({ ...s, phase: 'first_run' }))

    try {
      const companyName = stateRef.current.companyData?.name ?? 'this company'
      const res = await api.post<{ run_id: string }>('/skills/runs', {
        input_text: `Research ${companyName}`,
      })
      setState((s) => ({ ...s, skillRunId: res.run_id }))
    } catch (err) {
      setState((s) => ({
        ...s,
        phase: 'profile',
        error: err instanceof Error ? err.message : 'Failed to run skill',
      }))
    }
  }, [])

  const retry = useCallback(() => {
    setState({ ...initialState })
  }, [])

  return {
    ...state,
    startCrawl,
    runFirstSkill,
    retry,
  }
}

/** Parse company data from crawl output HTML (best-effort extraction) */
function parseCompanyData(html: string, url: string): CompanyData {
  // Create a temporary element to extract text from HTML
  const div = document.createElement('div')
  div.innerHTML = html

  // Try to extract structured data from the HTML
  const headings = div.querySelectorAll('h1, h2, h3')
  const paragraphs = div.querySelectorAll('p')
  const listItems = div.querySelectorAll('li')

  const name = headings[0]?.textContent?.trim() ?? new URL(url).hostname.replace('www.', '')
  const description = paragraphs[0]?.textContent?.trim() ?? ''

  // Extract details from list items or table rows
  const details: Record<string, string> = {}
  listItems.forEach((li) => {
    const text = li.textContent?.trim() ?? ''
    const colonIdx = text.indexOf(':')
    if (colonIdx > 0 && colonIdx < 40) {
      const key = text.slice(0, colonIdx).trim()
      const value = text.slice(colonIdx + 1).trim()
      if (key && value) details[key] = value
    }
  })

  return {
    name,
    description,
    industry: details['Industry'] ?? details['Sector'] ?? '',
    url,
    details,
  }
}
