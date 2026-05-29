import { useState, useCallback } from 'react'
import { Link, useParams } from 'react-router'
import {
  ArrowLeft,
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  Minus,
  Users,
  CalendarDays,
  Timer,
  ExternalLink,
  BookOpen,
  AlertCircle,
} from 'lucide-react'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { apiUrl } from '@/lib/api'
import { useSSE } from '@/lib/sse'
import { useMeetingDetail } from '../hooks/useMeetingDetail'
import { useMeetingProcessing } from '../hooks/useMeetingProcessing'
import { PrepBriefingPanel } from '@/features/relationships/components/PrepBriefingPanel'
import { prepMeeting, queryKeys } from '../api'
import type { ProcessingStatus, MeetingDetail } from '../types/meetings'

// ---------------------------------------------------------------------------
// Badge configs (same as MeetingCard — shared constants)
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  ProcessingStatus,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string; spin?: boolean }
> = {
  pending:    { icon: Clock,        color: 'var(--secondary-text)', label: 'Pending' },
  processing: { icon: Loader2,      color: '#3B82F6',               label: 'Processing', spin: true },
  complete:   { icon: CheckCircle2, color: 'var(--success, #16a34a)', label: 'Complete' },
  failed:     { icon: XCircle,      color: 'var(--error, #dc2626)',   label: 'Failed' },
  skipped:    { icon: Minus,        color: 'var(--secondary-text)', label: 'Skipped' },
  scheduled:  { icon: CalendarDays, color: '#3B82F6',               label: 'Scheduled' },
  recorded:   { icon: CheckCircle2, color: '#7c3aed',               label: 'Recorded' },
  cancelled:  { icon: XCircle,      color: 'var(--secondary-text)', label: 'Cancelled' },
}

const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  discovery:        { bg: 'rgba(59,130,246,0.1)',  text: '#2563eb' },
  prospect:         { bg: 'rgba(34,197,94,0.1)',   text: '#16a34a' },
  customer_feedback:{ bg: 'rgba(34,197,94,0.1)',   text: '#16a34a' },
  advisor:          { bg: 'rgba(168,85,247,0.1)',  text: '#7c3aed' },
  investor_pitch:   { bg: 'rgba(245,158,11,0.1)',  text: '#d97706' },
  internal:         { bg: 'rgba(107,114,128,0.1)', text: '#4b5563' },
  team_meeting:     { bg: 'rgba(107,114,128,0.1)', text: '#4b5563' },
  expert:           { bg: 'rgba(20,184,166,0.1)',  text: '#0f766e' },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMeetingDate(dateStr: string | null): string {
  if (!dateStr) return 'Unknown date'
  return new Date(dateStr).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function formatMeetingType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl p-6 mb-4"
      style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--subtle-border)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
      }}
    >
      <h2
        className="text-sm font-semibold uppercase tracking-wide mb-4"
        style={{ color: 'var(--secondary-text)' }}
      >
        {title}
      </h2>
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProcessingFeedback — for pending/failed/recorded meetings
// ---------------------------------------------------------------------------

function ProcessingFeedback({ meetingId, status }: { meetingId: string; status: ProcessingStatus }) {
  const { phase, currentStage, startProcessing } = useMeetingProcessing(meetingId)

  if (phase === 'processing') {
    return (
      <div
        className="rounded-xl p-6 mb-4 flex items-center gap-3"
        style={{ background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.2)' }}
      >
        <Loader2 className="size-5 animate-spin shrink-0" style={{ color: '#3B82F6' }} />
        <div>
          <p className="text-sm font-medium" style={{ color: '#2563eb' }}>Processing meeting...</p>
          {currentStage && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--secondary-text)' }}>{currentStage}</p>
          )}
        </div>
      </div>
    )
  }

  if (phase === 'complete') {
    return (
      <div
        className="rounded-xl p-6 mb-4 flex items-center gap-3"
        style={{ background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.2)' }}
      >
        <CheckCircle2 className="size-5 shrink-0" style={{ color: '#16a34a' }} />
        <p className="text-sm font-medium" style={{ color: '#16a34a' }}>Processing complete</p>
      </div>
    )
  }

  if (phase === 'error' || status === 'failed') {
    return (
      <div
        className="rounded-xl p-6 mb-4 flex items-center justify-between gap-3"
        style={{ background: 'rgba(220,38,38,0.05)', border: '1px solid rgba(220,38,38,0.2)' }}
      >
        <div className="flex items-center gap-3">
          <XCircle className="size-5 shrink-0" style={{ color: '#dc2626' }} />
          <p className="text-sm font-medium" style={{ color: '#dc2626' }}>
            {phase === 'error' ? 'Processing failed' : 'Previous processing attempt failed'}
          </p>
        </div>
        <button
          onClick={startProcessing}
          className="text-sm px-4 py-1.5 rounded-lg font-medium transition-opacity hover:opacity-80"
          style={{ background: 'rgba(220,38,38,0.1)', color: '#dc2626' }}
        >
          Retry
        </button>
      </div>
    )
  }

  // idle + pending
  if (status === 'pending') {
    return (
      <div
        className="rounded-xl p-6 mb-4 flex items-center justify-between gap-3"
        style={{ background: 'var(--brand-light)', border: '1px solid var(--brand-coral-20, rgba(233,77,53,0.2))' }}
      >
        <div>
          <p className="text-sm font-medium" style={{ color: 'var(--brand-coral)' }}>
            This meeting hasn't been processed yet
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--secondary-text)' }}>
            Processing extracts insights, action items, and links this meeting to your relationships.
          </p>
        </div>
        <button
          onClick={startProcessing}
          className="text-sm px-4 py-1.5 rounded-lg font-medium shrink-0 transition-opacity hover:opacity-80"
          style={{ background: 'var(--brand-coral)', color: '#fff' }}
        >
          Process
        </button>
      </div>
    )
  }

  // idle + recorded — offer to process
  if (status === 'recorded') {
    return (
      <div
        className="rounded-xl p-6 mb-4 flex items-center justify-between gap-3"
        style={{ background: 'rgba(124,58,237,0.05)', border: '1px solid rgba(124,58,237,0.2)' }}
      >
        <div>
          <p className="text-sm font-medium" style={{ color: '#7c3aed' }}>
            Meeting recorded — ready to process
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--secondary-text)' }}>
            Processing extracts insights, action items, and links this meeting to your relationships.
          </p>
        </div>
        <button
          onClick={startProcessing}
          className="text-sm px-4 py-1.5 rounded-lg font-medium shrink-0 transition-opacity hover:opacity-80"
          style={{ background: '#7c3aed', color: '#fff' }}
        >
          Process
        </button>
      </div>
    )
  }

  return null
}

// ---------------------------------------------------------------------------
// ScheduledPrepSection — 3-state component for meeting prep on scheduled/recorded
// ---------------------------------------------------------------------------

function ScheduledPrepSection({ meeting }: { meeting: MeetingDetail }) {
  // State C: account_id already available — use PrepBriefingPanel directly
  if (meeting.account_id) {
    return (
      <PrepBriefingPanel
        accountId={meeting.account_id}
        accountName="this account"
        meetingId={meeting.id}
      />
    )
  }

  // State A -> B managed by inner component
  return <PrepTrigger meetingId={meeting.id} />
}

function PrepTrigger({ meetingId }: { meetingId: string }) {
  const queryClient = useQueryClient()
  const [streamUrl, setStreamUrl] = useState<string | null>(null)
  const [briefingHtml, setBriefingHtml] = useState<string | null>(null)
  const [prepPhase, setPrepPhase] = useState<'idle' | 'streaming' | 'done' | 'error'>('idle')
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleEvent = useCallback(
    (event: { type: string; data: Record<string, unknown> }) => {
      switch (event.type) {
        case 'stage': {
          const message = (event.data.message as string) ?? ''
          if (message) setStatusMsg(message)
          break
        }
        case 'done': {
          const html =
            (event.data.rendered_html as string) ??
            (event.data.output as string) ??
            ''
          setBriefingHtml(html)
          setPrepPhase('done')
          setStreamUrl(null)
          // Invalidate meeting detail so account_id refreshes for subsequent page loads
          queryClient.invalidateQueries({ queryKey: queryKeys.meetings.detail(meetingId) })
          break
        }
        case 'error': {
          setErrorMsg((event.data.message as string) ?? 'Prep failed')
          setPrepPhase('error')
          setStreamUrl(null)
          break
        }
      }
    },
    [queryClient, meetingId],
  )

  useSSE(streamUrl, handleEvent)

  const mutation = useMutation({
    mutationFn: () => prepMeeting(meetingId),
    onSuccess: (res) => {
      // Immediately transition to streaming state with the stream_url from response
      setPrepPhase('streaming')
      setStatusMsg(null)
      setErrorMsg(null)
      setBriefingHtml(null)
      setStreamUrl(apiUrl(`/api/v1/skills/runs/${res.run_id}/stream`))
    },
    onError: (err: Error) => {
      // 400 = no account linkable
      if (err.message?.includes('400') || err.message?.includes('account')) {
        setErrorMsg('No company account could be linked. Add attendees with company emails.')
      } else {
        setErrorMsg(err.message ?? 'Failed to start prep')
      }
      setPrepPhase('error')
    },
  })

  // State A: idle — show prep trigger button
  if (prepPhase === 'idle') {
    return (
      <div className="mb-4">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-2 text-sm px-4 py-2 rounded-lg font-medium transition-opacity hover:opacity-85 disabled:opacity-60"
          style={{ background: 'var(--brand-coral)', color: '#fff' }}
        >
          {mutation.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <BookOpen className="size-4" />
          )}
          Prepare for this meeting
        </button>
      </div>
    )
  }

  // State B: streaming — show briefing as it streams
  if (prepPhase === 'streaming') {
    return (
      <div
        className="rounded-xl p-5 mb-4 flex items-center gap-3"
        style={{ background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.2)' }}
      >
        <Loader2 className="size-5 animate-spin shrink-0" style={{ color: '#3B82F6' }} />
        <div>
          <p className="text-sm font-medium" style={{ color: '#2563eb' }}>
            Preparing meeting briefing...
          </p>
          {statusMsg && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--secondary-text)' }}>
              {statusMsg}
            </p>
          )}
        </div>
      </div>
    )
  }

  // State B done: show rendered briefing HTML
  if (prepPhase === 'done' && briefingHtml) {
    return (
      <div
        className="rounded-xl mb-4 overflow-hidden"
        style={{ border: '1px solid var(--subtle-border)', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
      >
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{ background: 'var(--brand-light)', borderBottom: '1px solid rgba(233,77,53,0.15)' }}
        >
          <div className="flex items-center gap-2">
            <BookOpen className="size-4" style={{ color: 'var(--brand-coral)' }} />
            <span className="text-sm font-semibold" style={{ color: 'var(--heading-text)' }}>
              Meeting Prep
            </span>
          </div>
        </div>
        <div className="px-5 py-4" style={{ background: 'var(--card-bg)' }}>
          <div
            className="prose prose-sm max-w-none"
            style={{ color: 'var(--heading-text)', fontSize: '0.875rem', lineHeight: '1.6' }}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: briefingHtml }}
          />
        </div>
      </div>
    )
  }

  // Error state
  if (prepPhase === 'error') {
    return (
      <div
        className="rounded-xl p-5 mb-4 flex items-center justify-between gap-3"
        style={{ background: 'rgba(220,38,38,0.05)', border: '1px solid rgba(220,38,38,0.2)' }}
      >
        <div className="flex items-center gap-3">
          <AlertCircle className="size-5 shrink-0" style={{ color: '#dc2626' }} />
          <p className="text-sm font-medium" style={{ color: '#dc2626' }}>
            {errorMsg ?? 'Prep failed -- please try again'}
          </p>
        </div>
        <button
          onClick={() => { setPrepPhase('idle'); mutation.mutate() }}
          className="text-sm px-4 py-1.5 rounded-lg font-medium shrink-0 transition-opacity hover:opacity-80"
          style={{ background: 'rgba(220,38,38,0.1)', color: '#dc2626' }}
        >
          Retry
        </button>
      </div>
    )
  }

  return null
}

// ---------------------------------------------------------------------------
// MeetingDetailPage
// ---------------------------------------------------------------------------

export function MeetingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: meeting, isLoading } = useMeetingDetail(id)

  if (isLoading) {
    return (
      <div className="flex-1 overflow-y-auto" style={{ background: 'var(--page-bg)' }}>
        <div className="max-w-3xl mx-auto px-6 py-8 space-y-4">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <div className="h-32 rounded-xl" style={{ background: 'var(--card-bg)' }} />
          <div className="h-48 rounded-xl" style={{ background: 'var(--card-bg)' }} />
        </div>
      </div>
    )
  }

  if (!meeting) {
    return (
      <div className="flex-1 overflow-y-auto" style={{ background: 'var(--page-bg)' }}>
        <div className="max-w-3xl mx-auto px-6 py-8">
          <Link
            to="/meetings"
            className="flex items-center gap-1 text-sm mb-6 hover:opacity-80 transition-opacity"
            style={{ color: 'var(--secondary-text)' }}
          >
            <ArrowLeft className="size-4" />
            Back to Meetings
          </Link>
          <p style={{ color: 'var(--secondary-text)' }}>Meeting not found.</p>
        </div>
      </div>
    )
  }

  const statusCfg = STATUS_CONFIG[meeting.processing_status]
  const StatusIcon = statusCfg.icon
  const typeCfg = meeting.meeting_type ? TYPE_COLORS[meeting.meeting_type] : null
  const attendees = meeting.attendees ?? []

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: 'var(--page-bg)' }}>
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Back link */}
        <Link
          to="/meetings"
          className="flex items-center gap-1 text-sm mb-6 hover:opacity-80 transition-opacity"
          style={{ color: 'var(--secondary-text)' }}
        >
          <ArrowLeft className="size-4" />
          Back to Meetings
        </Link>

        {/* Header */}
        <div className="mb-6">
          <h1
            className="text-2xl font-bold mb-2"
            style={{ color: 'var(--heading-text)' }}
          >
            {meeting.title ?? 'Untitled meeting'}
          </h1>
          <div className="flex items-center gap-3 flex-wrap">
            {/* Date */}
            <span className="flex items-center gap-1 text-sm" style={{ color: 'var(--secondary-text)' }}>
              <CalendarDays className="size-4" />
              {formatMeetingDate(meeting.meeting_date)}
            </span>
            {/* Duration */}
            {meeting.duration_mins && (
              <span className="flex items-center gap-1 text-sm" style={{ color: 'var(--secondary-text)' }}>
                <Timer className="size-4" />
                {meeting.duration_mins} min
              </span>
            )}
            {/* Type badge */}
            {meeting.meeting_type && typeCfg && (
              <span
                className="text-sm px-2 py-0.5 rounded-full"
                style={{ background: typeCfg.bg, color: typeCfg.text }}
              >
                {formatMeetingType(meeting.meeting_type)}
              </span>
            )}
            {/* Status badge */}
            <span className="flex items-center gap-1 text-sm" style={{ color: statusCfg.color }}>
              <StatusIcon className={`size-4${statusCfg.spin ? ' animate-spin' : ''}`} />
              {statusCfg.label}
            </span>
          </div>
        </div>

        {/* Processing feedback (for pending/failed/recorded) */}
        {(meeting.processing_status === 'pending' || meeting.processing_status === 'failed' || meeting.processing_status === 'recorded') && (
          <ProcessingFeedback meetingId={meeting.id} status={meeting.processing_status} />
        )}

        {/* Meeting Prep — show for scheduled/recorded meetings OR when linked to account */}
        {(meeting.account_id || meeting.processing_status === 'scheduled' || meeting.processing_status === 'recorded') && (
          <ScheduledPrepSection meeting={meeting} />
        )}

        {/* Attendees section */}
        {attendees.length > 0 && (
          <Section title="Attendees">
            <div className="flex flex-wrap gap-2">
              {attendees.map((att, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm"
                  style={{
                    background: att.is_external ? 'rgba(59,130,246,0.05)' : 'var(--brand-light)',
                    border: `1px solid ${att.is_external ? 'rgba(59,130,246,0.15)' : 'rgba(233,77,53,0.15)'}`,
                  }}
                >
                  <Users className="size-3 shrink-0" style={{ color: 'var(--secondary-text)' }} />
                  <span style={{ color: 'var(--heading-text)' }}>
                    {att.name || att.email || 'Unknown'}
                  </span>
                  {att.is_external && (
                    <span className="text-xs" style={{ color: '#2563eb' }}>external</span>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Summary section — only when complete and summary exists */}
        {meeting.processing_status === 'complete' && meeting.summary && (
          <>
            {/* TLDR */}
            {meeting.summary.tldr && (
              <Section title="Summary">
                <p className="text-sm leading-relaxed" style={{ color: 'var(--heading-text)' }}>
                  {meeting.summary.tldr}
                </p>
              </Section>
            )}

            {/* Key Decisions */}
            {meeting.summary.key_decisions.length > 0 && (
              <Section title="Key Decisions">
                <ul className="space-y-2">
                  {meeting.summary.key_decisions.map((decision, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm">
                      <span
                        className="size-1.5 rounded-full mt-1.5 shrink-0"
                        style={{ background: 'var(--brand-coral)' }}
                      />
                      <span style={{ color: 'var(--heading-text)' }}>{decision}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Action Items */}
            {meeting.summary.action_items.length > 0 && (
              <Section title="Action Items">
                <ul className="space-y-3">
                  {meeting.summary.action_items.map((action, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm">
                      <span
                        className="size-1.5 rounded-full mt-1.5 shrink-0"
                        style={{ background: '#2563eb' }}
                      />
                      <div className="flex-1">
                        <span style={{ color: 'var(--heading-text)' }}>{action.item}</span>
                        {(action.owner || action.due) && (
                          <div className="flex gap-3 mt-0.5">
                            {action.owner && (
                              <span className="text-xs" style={{ color: 'var(--secondary-text)' }}>
                                Owner: {action.owner}
                              </span>
                            )}
                            {action.due && (
                              <span className="text-xs" style={{ color: 'var(--secondary-text)' }}>
                                Due: {action.due}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Pain Points */}
            {meeting.summary.pain_points.length > 0 && (
              <Section title="Pain Points">
                <ul className="space-y-2">
                  {meeting.summary.pain_points.map((point, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm">
                      <span
                        className="size-1.5 rounded-full mt-1.5 shrink-0"
                        style={{ background: '#d97706' }}
                      />
                      <span style={{ color: 'var(--heading-text)' }}>{point}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </>
        )}

        {/* Transcript section — owner-only (transcript_url present) */}
        {meeting.transcript_url && (
          <Section title="Transcript">
            <a
              href={meeting.transcript_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm hover:opacity-80 transition-opacity"
              style={{ color: 'var(--brand-coral)' }}
            >
              <ExternalLink className="size-4" />
              View full transcript
            </a>
          </Section>
        )}
      </div>
    </div>
  )
}
