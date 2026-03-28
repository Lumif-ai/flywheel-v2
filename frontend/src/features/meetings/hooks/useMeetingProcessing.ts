import { useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSSE } from '@/lib/sse'
import { processMeeting, queryKeys } from '../api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ProcessingPhase = 'idle' | 'processing' | 'complete' | 'error'

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useMeetingProcessing(meetingId: string) {
  const [phase, setPhase] = useState<ProcessingPhase>('idle')
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)

  const queryClient = useQueryClient()

  // ---- SSE handler ----
  const handleEvent = useCallback(
    (event: { type: string; data: Record<string, unknown> }) => {
      switch (event.type) {
        case 'stage': {
          const message = (event.data.message as string) ?? ''
          if (message) setCurrentStage(message)
          break
        }
        case 'done': {
          setPhase('complete')
          setCurrentStage(null)
          setSseUrl(null)
          // Invalidate detail to get updated processing_status + fresh summary
          queryClient.invalidateQueries({ queryKey: queryKeys.meetings.detail(meetingId) })
          // Invalidate list to refresh status badges
          queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
          // Invalidate signals so badges refresh
          queryClient.invalidateQueries({ queryKey: ['signals'] })
          break
        }
        case 'error': {
          setPhase('error')
          setCurrentStage(null)
          setSseUrl(null)
          break
        }
      }
    },
    [queryClient, meetingId],
  )

  useSSE(sseUrl, handleEvent)

  // ---- Actions ----

  const startProcessing = useCallback(async () => {
    setPhase('processing')
    setCurrentStage(null)
    try {
      // POST first to get run_id, then set SSE URL
      const res = await processMeeting(meetingId)
      setSseUrl(`/api/v1/skills/runs/${res.run_id}/stream`)
    } catch (err) {
      setPhase('error')
      setCurrentStage(null)
    }
  }, [meetingId])

  return { phase, currentStage, startProcessing }
}
