import { useState, useCallback } from 'react'
import { useSSE } from '@/lib/sse'
import { triggerRelationshipPrep } from '../api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PrepPhase = 'idle' | 'running' | 'done' | 'error'

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useRelationshipPrep(accountId: string) {
  const [phase, setPhase] = useState<PrepPhase>('idle')
  const [status, setStatus] = useState<string | null>(null)
  const [briefingHtml, setBriefingHtml] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)

  const handleEvent = useCallback(
    (event: { type: string; data: Record<string, unknown> }) => {
      switch (event.type) {
        case 'stage': {
          const message = (event.data.message as string) ?? ''
          if (message) setStatus(message)
          break
        }
        case 'done': {
          // Account-scoped prep stores HTML in rendered_html on SkillRun
          // The done event data includes rendered_html
          const html =
            (event.data.rendered_html as string) ??
            (event.data.output as string) ??
            ''
          setBriefingHtml(html)
          setPhase('done')
          setSseUrl(null)
          break
        }
        case 'error': {
          setError((event.data.message as string) ?? 'Prep failed')
          setPhase('error')
          setSseUrl(null)
          break
        }
      }
    },
    [],
  )

  useSSE(sseUrl, handleEvent)

  const startPrep = useCallback(
    async (meetingId?: string) => {
      setPhase('running')
      setError(null)
      setBriefingHtml(null)
      setStatus(null)
      try {
        const res = await triggerRelationshipPrep(accountId, meetingId)
        setSseUrl(`/api/v1/skills/runs/${res.run_id}/stream`)
      } catch {
        setPhase('error')
        setError('Failed to start prep')
      }
    },
    [accountId],
  )

  const reset = useCallback(() => {
    setPhase('idle')
    setStatus(null)
    setBriefingHtml(null)
    setError(null)
    setSseUrl(null)
  }, [])

  return { phase, status, briefingHtml, error, startPrep, reset }
}
