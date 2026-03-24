/**
 * MomentExperience - Fourth onboarding moment.
 *
 * User enters a LinkedIn URL and optional agenda.
 * Triggers meeting-prep skill execution via SSE.
 * Shows briefing building section by section with progressive reveal.
 */

import { useState, useCallback } from 'react'
import { Linkedin, Calendar, ArrowRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useSSE } from '@/lib/sse'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { animationClasses } from '@/lib/animations'
import type { SSEEvent } from '@/types/events'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MomentExperienceProps {
  onComplete: (briefingHtml?: string) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MomentExperience({ onComplete }: MomentExperienceProps) {
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [agenda, setAgenda] = useState('')
  const [phase, setPhase] = useState<'input' | 'running' | 'done'>('input')
  const [status, setStatus] = useState<string | null>(null)
  const [renderedHtml, setRenderedHtml] = useState<string | null>(null)
  const [outputText, setOutputText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)

  // SSE handler for meeting prep events
  const handleEvent = useCallback(
    (event: SSEEvent) => {
      const data = event.data as Record<string, unknown>

      switch (event.type) {
        case 'stage':
          setStatus((data.message as string) ?? null)
          break
        case 'done': {
          const doneStatus = data.status as string
          const doneError = data.error as string | null
          if (doneStatus === 'failed' && doneError) {
            setError(doneError)
            setPhase('input')
            setSseUrl(null)
            setStatus(null)
            break
          }
          const html = (data.rendered_html as string) ?? ''
          const output = (data.output as string) ?? ''
          if (html) setRenderedHtml(html)
          if (output) setOutputText(output)
          setPhase('done')
          setSseUrl(null)
          setStatus(null)
          // Auto-advance with the briefing HTML
          const briefing = html || output || undefined
          setTimeout(() => onComplete(briefing), 500)
          break
        }
        case 'error':
          setError((data.message as string) ?? 'Meeting prep failed')
          setPhase('input')
          setSseUrl(null)
          setStatus(null)
          break
      }
    },
    [onComplete],
  )

  useSSE(sseUrl, handleEvent)

  // Start meeting prep skill run
  const startPrep = async () => {
    if (!linkedinUrl.trim()) return

    setPhase('running')
    setError(null)
    setStatus('Starting meeting prep...')

    try {
      const res = await api.post<{ run_id: string }>('/onboarding/meeting-prep', {
        linkedin_url: linkedinUrl.trim(),
        agenda: agenda.trim(),
        meeting_type: 'discovery',
      })

      setSseUrl(`/api/v1/onboarding/run/${res.run_id}/stream`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start meeting prep')
      setPhase('input')
    }
  }

  // ---- Input phase ----
  if (phase === 'input') {
    return (
      <div
        className={animationClasses.fadeSlideUp}
        style={{
          maxWidth: spacing.maxReading,
          width: '100%',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: spacing.section }}>
          <h1
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              lineHeight: typography.pageTitle.lineHeight,
              color: colors.headingText,
              marginBottom: spacing.tight,
            }}
          >
            Prepare for your next meeting
          </h1>
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            Drop a LinkedIn profile and we'll build a briefing in seconds
          </p>
        </div>

        {error && (
          <div
            className="rounded-lg p-3 text-center mb-4"
            style={{
              border: `1px solid ${colors.error}`,
              background: 'rgba(239,68,68,0.05)',
            }}
          >
            <p className="text-sm" style={{ color: colors.error }}>
              {error}
            </p>
          </div>
        )}

        {/* LinkedIn URL */}
        <div style={{ marginBottom: spacing.element }}>
          <label
            className="flex items-center gap-2 mb-2"
            style={{
              fontSize: typography.caption.size,
              fontWeight: '500',
              color: colors.headingText,
            }}
          >
            <Linkedin className="h-4 w-4 text-[#0A66C2]" />
            LinkedIn profile URL
          </label>
          <input
            type="url"
            value={linkedinUrl}
            onChange={(e) => setLinkedinUrl(e.target.value)}
            placeholder="https://linkedin.com/in/jane-smith"
            className="w-full rounded-lg border px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            style={{
              background: colors.cardBg,
              borderColor: colors.subtleBorder,
            }}
            onKeyDown={(e) => e.key === 'Enter' && startPrep()}
          />
        </div>

        {/* Agenda */}
        <div style={{ marginBottom: spacing.section }}>
          <label
            className="flex items-center gap-2 mb-2"
            style={{
              fontSize: typography.caption.size,
              fontWeight: '500',
              color: colors.headingText,
            }}
          >
            <Calendar className="h-4 w-4" style={{ color: colors.secondaryText }} />
            Brief agenda
            <span style={{ fontWeight: '400', color: colors.secondaryText }}>(optional)</span>
          </label>
          <textarea
            value={agenda}
            onChange={(e) => setAgenda(e.target.value)}
            placeholder="e.g. Introductory call to discuss partnership opportunities"
            rows={2}
            className="w-full rounded-lg border px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            style={{
              background: colors.cardBg,
              borderColor: colors.subtleBorder,
            }}
          />
        </div>

        <Button
          onClick={startPrep}
          disabled={!linkedinUrl.trim()}
          size="lg"
          className="w-full gap-2"
          style={{
            background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
            border: 'none',
            color: 'white',
          }}
        >
          Prepare briefing
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    )
  }

  // ---- Running phase ----
  return (
    <div
      className={animationClasses.fadeSlideUp}
      style={{
        maxWidth: spacing.maxReading,
        width: '100%',
        margin: '0 auto',
        textAlign: 'center',
      }}
    >
      <div style={{ marginBottom: spacing.section }}>
        <Loader2
          className="h-8 w-8 animate-spin mx-auto mb-4"
          style={{ color: colors.brandCoral }}
        />
        <h1
          style={{
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
            lineHeight: typography.pageTitle.lineHeight,
            color: colors.headingText,
            marginBottom: spacing.tight,
          }}
        >
          Building your briefing
        </h1>
        {status && (
          <p
            className="animate-pulse"
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            {status}
          </p>
        )}
      </div>

      <div
        className="rounded-lg p-4 text-left space-y-2"
        style={{
          border: `1px solid ${colors.subtleBorder}`,
          background: colors.brandTint,
        }}
      >
        <div className="flex items-center gap-2 text-sm">
          <Linkedin className="h-4 w-4 text-[#0A66C2]" />
          <span className="truncate" style={{ color: colors.secondaryText }}>
            {linkedinUrl}
          </span>
        </div>
        {agenda && (
          <div className="flex items-start gap-2 text-sm">
            <Calendar className="h-4 w-4 mt-0.5" style={{ color: colors.secondaryText }} />
            <span style={{ color: colors.secondaryText }}>{agenda}</span>
          </div>
        )}
      </div>
    </div>
  )
}
