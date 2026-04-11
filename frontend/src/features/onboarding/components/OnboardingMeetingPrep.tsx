/**
 * OnboardingMeetingPrep - First skill experience during onboarding.
 *
 * User enters a LinkedIn URL + brief agenda for an upcoming call.
 * Kicks off meeting-prep skill, streams results via SSE, shows
 * the briefing as the "aha moment" before moving to the workspace.
 */

import { useState, useCallback } from 'react'
import { Linkedin, Calendar, ArrowRight, Loader2, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useSSE } from '@/lib/sse'
import type { SSEEvent } from '@/types/events'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OnboardingMeetingPrepProps {
  onComplete: (briefingHtml?: string) => void
  onSkip: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OnboardingMeetingPrep({ onComplete, onSkip }: OnboardingMeetingPrepProps) {
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [agenda, setAgenda] = useState('')
  const [phase, setPhase] = useState<'input' | 'running' | 'done'>('input')
  const [status, setStatus] = useState<string | null>(null)
  const [renderedHtml, setRenderedHtml] = useState<string | null>(null)
  const [outputText, setOutputText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)

  // SSE handler for meeting prep events
  const handleEvent = useCallback((event: SSEEvent) => {
    const data = event.data as Record<string, unknown>

    switch (event.type) {
      case 'stage':
        setStatus((data.message as string) ?? null)
        break
      case 'text':
        // Accumulate output text if needed
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
        if (html) {
          setRenderedHtml(html)
        }
        if (output) {
          setOutputText(output)
        }
        setPhase('done')
        setSseUrl(null)
        setStatus(null)
        break
      }
      case 'error':
        setError((data.message as string) ?? 'Meeting prep failed')
        setPhase('input')
        setSseUrl(null)
        setStatus(null)
        break
    }
  }, [])

  useSSE(sseUrl, handleEvent)

  // Start meeting prep
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

  // ---------------------------------------------------------------------------
  // Render: input state
  // ---------------------------------------------------------------------------
  if (phase === 'input') {
    return (
      <div className="max-w-xl mx-auto space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Prepare for your next meeting
          </h2>
          <p className="text-muted-foreground">
            Drop a LinkedIn profile and we'll build you a briefing in seconds
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-center">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* LinkedIn URL input */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground flex items-center gap-2">
            <Linkedin className="h-4 w-4 text-[#0A66C2]" />
            LinkedIn profile URL
          </label>
          <input
            type="url"
            value={linkedinUrl}
            onChange={(e) => setLinkedinUrl(e.target.value)}
            placeholder="https://linkedin.com/in/jane-smith"
            className="w-full rounded-lg border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            onKeyDown={(e) => e.key === 'Enter' && startPrep()}
          />
        </div>

        {/* Agenda input */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            Brief agenda <span className="text-muted-foreground font-normal">(optional)</span>
          </label>
          <textarea
            value={agenda}
            onChange={(e) => setAgenda(e.target.value)}
            placeholder="e.g. Introductory call to discuss partnership opportunities"
            rows={2}
            className="w-full rounded-lg border bg-background px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>

        {/* Actions */}
        <Button
          onClick={startPrep}
          disabled={!linkedinUrl.trim()}
          size="lg"
          className="w-full gap-2"
        >
          Prepare briefing
          <ArrowRight className="h-4 w-4" />
        </Button>

        <div className="text-center">
          <button
            type="button"
            onClick={onSkip}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip — I'll try this later
          </button>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Render: running state
  // ---------------------------------------------------------------------------
  if (phase === 'running') {
    return (
      <div className="max-w-xl mx-auto text-center space-y-6">
        <div className="space-y-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Building your briefing
          </h2>
          {status && (
            <p className="text-sm text-muted-foreground animate-pulse">
              {status}
            </p>
          )}
        </div>

        <div className="rounded-lg border border-border/50 bg-muted/20 p-4 text-left space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <Linkedin className="h-4 w-4 text-[#0A66C2]" />
            <span className="text-muted-foreground truncate">{linkedinUrl}</span>
          </div>
          {agenda && (
            <div className="flex items-start gap-2 text-sm">
              <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
              <span className="text-muted-foreground">{agenda}</span>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Render: done state — show briefing
  // ---------------------------------------------------------------------------
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
          <FileText className="h-6 w-6 text-green-600 dark:text-green-400" />
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">
          Your briefing is ready
        </h2>
        <p className="text-muted-foreground">
          This is what Flywheel does — every meeting, every contact, smarter over time
        </p>
      </div>

      {/* Briefing content */}
      {renderedHtml ? (
        <div
          className="rounded-lg border border-border bg-background p-6 max-h-[32rem] overflow-y-auto prose prose-sm dark:prose-invert"
          dangerouslySetInnerHTML={{ __html: renderedHtml }}
        />
      ) : outputText ? (
        <div className="rounded-lg border border-border bg-background p-6 max-h-[32rem] overflow-y-auto">
          <div className="prose prose-sm dark:prose-invert whitespace-pre-wrap">
            {outputText}
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-muted/20 p-6 text-center">
          <p className="text-muted-foreground">
            Briefing generated — view it in your workspace
          </p>
        </div>
      )}

      <div className="flex gap-3">
        <Button onClick={() => onComplete(renderedHtml || outputText || undefined)} size="lg" className="flex-1 gap-2">
          View full briefing
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
