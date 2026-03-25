import { useState } from 'react'
import { Link } from 'react-router'
import {
  Plug2,
  PencilLine,
  Search,
  X,
  ArrowRight,
  Loader2,
  Check,
  Sparkles,
} from 'lucide-react'
import type { NudgeResponse } from '@/types/streams'
import {
  useNudgeDismiss,
  useNudgeSubmit,
  useNudgeResearch,
} from '../hooks/useBriefing'
import { CalendarNudge } from './CalendarNudge'

interface NudgeCardProps {
  nudge: NudgeResponse
}

export function NudgeCard({ nudge }: NudgeCardProps) {
  const [dismissed, setDismissed] = useState(false)
  const dismissMutation = useNudgeDismiss()

  const handleDismiss = () => {
    setDismissed(true)
    dismissMutation.mutate({
      nudge_type: nudge.type,
      nudge_key: nudge.key,
    })
  }

  if (dismissed) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 text-center text-sm text-muted-foreground opacity-60 transition-opacity duration-300">
        Dismissed
      </div>
    )
  }

  switch (nudge.type) {
    case 'calendar_meeting_prep':
      return (
        <CalendarNudge
          attendeeName={nudge.action_payload?.attendee_name}
          companyName={nudge.action_payload?.company_name ?? 'your meeting'}
          meetingDay={nudge.action_payload?.scheduled_at
            ? new Date(nudge.action_payload.scheduled_at).toLocaleDateString('en-US', { weekday: 'long' })
            : 'soon'}
          meetingId={nudge.action_payload?.meeting_id ?? ''}
          nudgeKey={nudge.key}
          body={nudge.body}
          onDismiss={handleDismiss}
        />
      )
    case 'integration_connect':
      return (
        <IntegrationConnectNudge nudge={nudge} onDismiss={handleDismiss} />
      )
    case 'knowledge_gap':
      return <KnowledgeGapNudge nudge={nudge} onDismiss={handleDismiss} />
    case 'context_enrichment':
      return <EnrichmentNudge nudge={nudge} onDismiss={handleDismiss} />
    default:
      return null
  }
}

// ---------------------------------------------------------------------------
// Shared dismiss button
// ---------------------------------------------------------------------------

function DismissButton({ onDismiss }: { onDismiss: () => void }) {
  return (
    <button
      onClick={onDismiss}
      className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground/50 opacity-0 transition-opacity hover:bg-muted hover:text-foreground group-hover:opacity-100"
      title="Dismiss nudge"
    >
      <X className="h-3.5 w-3.5" />
    </button>
  )
}

// ---------------------------------------------------------------------------
// Integration connect variant
// ---------------------------------------------------------------------------

function IntegrationConnectNudge({
  nudge,
  onDismiss,
}: {
  nudge: NudgeResponse
  onDismiss: () => void
}) {
  return (
    <div className="group relative rounded-xl border border-blue-200 bg-blue-50/50 p-4">
      <DismissButton onDismiss={onDismiss} />
      <div className="flex items-start gap-3">
        <Plug2 className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
        <div className="min-w-0 flex-1">
          <h3 className="font-medium leading-tight text-blue-900">
            {nudge.title}
          </h3>
          <p className="mt-1 text-sm text-blue-700">{nudge.body}</p>
          <div className="mt-3">
            <Link
              to="/settings"
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              {nudge.action_label ?? 'Connect'}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Knowledge gap variant
// ---------------------------------------------------------------------------

function KnowledgeGapNudge({
  nudge,
  onDismiss,
}: {
  nudge: NudgeResponse
  onDismiss: () => void
}) {
  const [text, setText] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const submitMutation = useNudgeSubmit()

  const handleSubmit = () => {
    if (!text.trim() || !nudge.stream_id) return
    submitMutation.mutate(
      {
        nudge_key: nudge.key,
        stream_id: nudge.stream_id,
        text: text.trim(),
      },
      {
        onSuccess: () => setSubmitted(true),
      },
    )
  }

  if (submitted) {
    return (
      <div className="rounded-xl border border-green-200 bg-green-50/50 p-4 text-center transition-opacity duration-300">
        <div className="flex items-center justify-center gap-2 text-sm font-medium text-green-700">
          <Check className="h-4 w-4" />
          Added!
        </div>
      </div>
    )
  }

  return (
    <div className="group relative rounded-xl border border-amber-200 bg-amber-50/50 p-4">
      <DismissButton onDismiss={onDismiss} />
      <div className="flex items-start gap-3">
        <PencilLine className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <div className="min-w-0 flex-1">
          <h3 className="font-medium leading-tight text-amber-900">
            {nudge.title}
          </h3>
          <p className="mt-1 text-sm text-amber-700">{nudge.body}</p>
          <div className="mt-3 flex items-center gap-2">
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="Type a quick note..."
              className="flex-1 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm placeholder:text-amber-400 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
            <button
              onClick={handleSubmit}
              disabled={!text.trim() || submitMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-amber-700 disabled:opacity-50"
            >
              {submitMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                'Submit'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Enrichment variant
// ---------------------------------------------------------------------------

function EnrichmentNudge({
  nudge,
  onDismiss,
}: {
  nudge: NudgeResponse
  onDismiss: () => void
}) {
  const [mode, setMode] = useState<'idle' | 'typing' | 'researching' | 'done'>(
    'idle',
  )
  const [text, setText] = useState('')
  const [resultMessage, setResultMessage] = useState('')
  const submitMutation = useNudgeSubmit()
  const researchMutation = useNudgeResearch()

  const handleSubmitText = () => {
    if (!text.trim() || !nudge.stream_id) return
    submitMutation.mutate(
      {
        nudge_key: nudge.key,
        stream_id: nudge.stream_id,
        text: text.trim(),
      },
      {
        onSuccess: () => {
          setResultMessage('Added!')
          setMode('done')
        },
      },
    )
  }

  const handleResearch = () => {
    if (!nudge.entity_id || !nudge.entity_name) return
    setMode('researching')
    researchMutation.mutate(
      {
        nudge_key: nudge.key,
        entity_id: nudge.entity_id,
        entity_name: nudge.entity_name,
      },
      {
        onSuccess: () => {
          setResultMessage(
            'Research started! Results will appear in your next briefing.',
          )
          setMode('done')
        },
        onError: (error) => {
          const msg =
            error instanceof Error ? error.message : 'Research failed'
          if (
            msg.toLowerCase().includes('api key') ||
            msg.toLowerCase().includes('byok')
          ) {
            setResultMessage('Add an API key in Settings to enable research.')
          } else {
            setResultMessage(msg)
          }
          setMode('done')
        },
      },
    )
  }

  if (mode === 'done') {
    const isSuccess =
      resultMessage === 'Added!' || resultMessage.includes('Research started')
    return (
      <div
        className={`rounded-xl border p-4 text-center transition-opacity duration-300 ${
          isSuccess
            ? 'border-green-200 bg-green-50/50'
            : 'border-red-200 bg-red-50/50'
        }`}
      >
        <div
          className={`flex items-center justify-center gap-2 text-sm font-medium ${
            isSuccess ? 'text-green-700' : 'text-red-700'
          }`}
        >
          {isSuccess && <Check className="h-4 w-4" />}
          {resultMessage}
          {resultMessage.includes('Settings') && (
            <Link
              to="/settings"
              className="ml-1 underline hover:no-underline"
            >
              Go to Settings
            </Link>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="group relative rounded-xl border border-purple-200 bg-purple-50/50 p-4">
      <DismissButton onDismiss={onDismiss} />
      <div className="flex items-start gap-3">
        <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-purple-600" />
        <div className="min-w-0 flex-1">
          <h3 className="font-medium leading-tight text-purple-900">
            {nudge.title}
          </h3>
          <p className="mt-1 text-sm text-purple-700">{nudge.body}</p>

          {mode === 'typing' ? (
            <div className="mt-3 flex items-center gap-2">
              <input
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmitText()}
                placeholder="Type a quick note..."
                autoFocus
                className="flex-1 rounded-lg border border-purple-300 bg-white px-3 py-1.5 text-sm placeholder:text-purple-400 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
              />
              <button
                onClick={handleSubmitText}
                disabled={!text.trim() || submitMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-purple-700 disabled:opacity-50"
              >
                {submitMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  'Submit'
                )}
              </button>
            </div>
          ) : (
            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={() => setMode('typing')}
                className="inline-flex items-center gap-1.5 rounded-lg border border-purple-300 bg-white px-3 py-1.5 text-sm font-medium text-purple-700 transition-colors hover:bg-purple-50"
              >
                <PencilLine className="h-3.5 w-3.5" />
                Type
              </button>

              {nudge.has_research_action && (
                <button
                  onClick={handleResearch}
                  disabled={researchMutation.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-purple-700 disabled:opacity-50"
                  title={
                    !nudge.has_research_action
                      ? 'Add API key in Settings to enable research'
                      : undefined
                  }
                >
                  {researchMutation.isPending ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Researching...
                    </>
                  ) : (
                    <>
                      <Search className="h-3.5 w-3.5" />
                      Research for me
                    </>
                  )}
                </button>
              )}

              <button
                onClick={onDismiss}
                className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted"
              >
                Skip
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
