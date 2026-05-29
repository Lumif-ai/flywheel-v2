import { useState, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, apiUrl } from '@/lib/api'
import { useSSE } from '@/lib/sse'
import type { CrawlItem } from '@/features/onboarding/hooks/useOnboarding'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ProfileRefreshPhase = 'idle' | 'refreshing' | 'complete' | 'error'

interface ProfileRefreshError {
  message: string
  retryable: boolean
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useProfileRefresh() {
  const [phase, setPhase] = useState<ProfileRefreshPhase>('idle')
  const [crawlItems, setCrawlItems] = useState<CrawlItem[]>([])
  const [crawlTotal, setCrawlTotal] = useState(0)
  const [crawlStatus, setCrawlStatus] = useState<string | null>(null)
  const [error, setError] = useState<ProfileRefreshError | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)

  const queryClient = useQueryClient()
  const crawlItemsRef = useRef(crawlItems)
  crawlItemsRef.current = crawlItems

  // ---- SSE handler ----
  const handleEvent = useCallback(
    (event: { type: string; data: Record<string, unknown> }) => {
      switch (event.type) {
        case 'stage': {
          const message = (event.data.message as string) ?? ''
          if (message) setCrawlStatus(message)
          break
        }
        case 'discovery': {
          const item: CrawlItem = {
            category: (event.data.category as string) ?? 'company_info',
            icon: (event.data.icon as string) ?? 'Building2',
            label: (event.data.label as string) ?? '',
            items: (event.data.items as string[]) ?? [],
            count:
              (event.data.count as number) ??
              crawlItemsRef.current.length + 1,
          }
          setCrawlItems((prev) => [...prev, item])
          setCrawlTotal((prev) => prev + item.items.length)
          setCrawlStatus(null)
          break
        }
        case 'text': {
          // Backward compat — handle same as discovery
          const item: CrawlItem = {
            category: (event.data.category as string) ?? 'company_info',
            icon: (event.data.icon as string) ?? 'Building2',
            label: (event.data.label as string) ?? '',
            items: (event.data.items as string[]) ?? [],
            count:
              (event.data.count as number) ??
              crawlItemsRef.current.length + 1,
          }
          setCrawlItems((prev) => [...prev, item])
          setCrawlTotal((prev) => prev + item.items.length)
          setCrawlStatus(null)
          break
        }
        case 'done': {
          setPhase('complete')
          setCrawlStatus(null)
          setSseUrl(null)
          queryClient.invalidateQueries({ queryKey: ['company-profile'] })
          break
        }
        case 'crawl_error': {
          const errorMsg =
            (event.data.error as string) ?? 'Refresh failed'
          const retryable = (event.data.retryable as boolean) ?? false
          setPhase('error')
          setError({ message: errorMsg, retryable })
          setCrawlStatus(null)
          setSseUrl(null)
          break
        }
        case 'error': {
          setPhase('error')
          setError({
            message:
              (event.data.message as string) ?? 'Connection lost',
            retryable: true,
          })
          setCrawlStatus(null)
          setSseUrl(null)
          break
        }
      }
    },
    [queryClient],
  )

  useSSE(sseUrl, handleEvent)

  // ---- Actions ----

  const startRefresh = useCallback(async () => {
    setPhase('refreshing')
    setCrawlItems([])
    setCrawlTotal(0)
    setCrawlStatus(null)
    setError(null)

    try {
      const res = await api.post<{ run_id: string }>('/profile/refresh', {})
      setSseUrl(apiUrl(`/api/v1/skills/runs/${res.run_id}/stream`))
    } catch (err) {
      setPhase('error')
      setError({
        message:
          err instanceof Error ? err.message : 'Failed to start refresh',
        retryable: true,
      })
    }
  }, [])

  const startReset = useCallback(async () => {
    setError(null)

    try {
      await api.post<{ deleted_count: number }>('/profile/reset', {})
      // Clear cache immediately so UI shows blank state, then mark stale
      // so next navigation/focus triggers a fresh fetch
      queryClient.setQueryData(['company-profile'], {
        company_name: null,
        domain: null,
        groups: [],
        product_tabs: [],
        total_items: 0,
        last_updated: null,
        uploaded_files: [],
        enrichment_status: null,
      })
      queryClient.invalidateQueries({ queryKey: ['company-profile'] })
      setPhase('idle')
    } catch (err) {
      setPhase('error')
      setError({
        message:
          err instanceof Error ? err.message : 'Failed to reset profile',
        retryable: true,
      })
    }
  }, [queryClient])

  const startFromRunId = useCallback((runId: string) => {
    setPhase('refreshing')
    setCrawlItems([])
    setCrawlTotal(0)
    setCrawlStatus(null)
    setError(null)
    setSseUrl(apiUrl(`/api/v1/skills/runs/${runId}/stream`))
  }, [])

  const dismiss = useCallback(() => {
    setPhase('idle')
    setCrawlItems([])
    setCrawlTotal(0)
    setCrawlStatus(null)
    setError(null)
    setSseUrl(null)
  }, [])

  return {
    phase,
    crawlItems,
    crawlTotal,
    crawlStatus,
    error,
    startRefresh,
    startReset,
    startFromRunId,
    dismiss,
  }
}
