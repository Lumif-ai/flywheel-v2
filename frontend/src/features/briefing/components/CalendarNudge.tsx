import { useState } from 'react'
import { CalendarDays, ArrowRight, X, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router'
import { useNudgeDismiss } from '../hooks/useBriefing'
import { api } from '@/lib/api'

interface CalendarNudgeProps {
  attendeeName?: string
  companyName: string
  meetingDay: string
  meetingId: string
  nudgeKey: string
  body: string
  onPrepare?: () => void
  onDismiss?: () => void
}

export function CalendarNudge({
  companyName,
  meetingId,
  nudgeKey,
  body,
  onPrepare,
  onDismiss,
}: CalendarNudgeProps) {
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState(false)
  const [preparing, setPreparing] = useState(false)
  const dismissMutation = useNudgeDismiss()

  const handleDismiss = () => {
    setDismissed(true)
    dismissMutation.mutate({
      nudge_type: 'calendar_meeting_prep',
      nudge_key: nudgeKey,
    })
    onDismiss?.()
  }

  const handlePrepare = async () => {
    setPreparing(true)
    try {
      // Trigger a meeting-prep skill run via chat endpoint
      const result = await api.post<{ id: string }>('/skills/run', {
        skill_slug: 'company-intel',
        input: companyName,
        metadata: { meeting_id: meetingId, source: 'calendar_nudge' },
      })
      onPrepare?.()
      // Navigate to the skill run result
      if (result?.id) {
        navigate(`/briefing/${result.id}`)
      }
    } catch {
      // Fallback: navigate to chat with prefilled query
      navigate(`/?q=${encodeURIComponent(`Prepare a briefing for ${companyName}`)}`)
    } finally {
      setPreparing(false)
    }
  }

  if (dismissed) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 text-center text-sm text-muted-foreground opacity-60 transition-opacity duration-300">
        Dismissed
      </div>
    )
  }

  return (
    <div className="group relative rounded-xl border border-orange-200 bg-gradient-to-r from-orange-50/80 to-amber-50/60 p-4 animate-in slide-in-from-top-2 duration-300">
      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground/50 opacity-0 transition-opacity hover:bg-muted hover:text-foreground group-hover:opacity-100"
        title="Not now"
      >
        <X className="h-3.5 w-3.5" />
      </button>

      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-orange-100">
          <CalendarDays className="h-4.5 w-4.5 text-orange-600" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-relaxed text-foreground">
            {body}
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={handlePrepare}
              disabled={preparing}
              className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium text-white transition-all hover:shadow-md hover:-translate-y-px disabled:opacity-50"
              style={{
                background: 'linear-gradient(135deg, var(--brand-coral), var(--brand-gradient-end, #E94D35))',
              }}
            >
              {preparing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Preparing...
                </>
              ) : (
                <>
                  Prepare briefing
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
            <button
              onClick={handleDismiss}
              className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted"
            >
              Not now
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
