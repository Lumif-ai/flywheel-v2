import { useNavigate } from 'react-router'
import { Clock, Loader2, CheckCircle2, XCircle, Minus, Users, CalendarDays } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import type { MeetingListItem, ProcessingStatus } from '../types/meetings'
import { useMeetingProcessing } from '../hooks/useMeetingProcessing'

// ---------------------------------------------------------------------------
// Badge configs
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

function formatRelativeDate(dateStr: string | null): string {
  if (!dateStr) return 'Unknown date'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  // Future dates
  if (diffMs < 0) {
    const futureDiffMs = Math.abs(diffMs)
    const futureDiffHours = Math.floor(futureDiffMs / (1000 * 60 * 60))
    const futureDiffDays = Math.floor(futureDiffMs / (1000 * 60 * 60 * 24))

    if (futureDiffHours < 1) return 'Soon'
    if (futureDiffHours < 24) return `In ${futureDiffHours} hour${futureDiffHours !== 1 ? 's' : ''}`
    if (futureDiffDays === 1) return 'Tomorrow'
    if (futureDiffDays < 7) return `In ${futureDiffDays} days`
    if (futureDiffDays < 30) return `In ${Math.floor(futureDiffDays / 7)} week${Math.floor(futureDiffDays / 7) === 1 ? '' : 's'}`
    return `In ${Math.floor(futureDiffDays / 30)} month${Math.floor(futureDiffDays / 30) === 1 ? '' : 's'}`
  }

  // Past dates
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) === 1 ? '' : 's'} ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} month${Math.floor(diffDays / 30) === 1 ? '' : 's'} ago`
  return `${Math.floor(diffDays / 365)} year${Math.floor(diffDays / 365) === 1 ? '' : 's'} ago`
}

function formatMeetingType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// ---------------------------------------------------------------------------
// ProcessButton — isolated so each card has its own processing state
// ---------------------------------------------------------------------------

function ProcessButton({ meetingId, status }: { meetingId: string; status: ProcessingStatus }) {
  const { phase, currentStage, startProcessing } = useMeetingProcessing(meetingId)

  if (status !== 'pending' && phase === 'idle') return null

  if (phase === 'processing' || (status === 'processing' && phase === 'idle')) {
    return (
      <span
        className="text-xs flex items-center gap-1"
        style={{ color: '#3B82F6' }}
      >
        <Loader2 className="size-3 animate-spin" />
        {currentStage ?? 'Processing...'}
      </span>
    )
  }

  if (phase === 'complete') {
    return (
      <span className="text-xs flex items-center gap-1" style={{ color: 'var(--success, #16a34a)' }}>
        <CheckCircle2 className="size-3" />
        Done
      </span>
    )
  }

  if (phase === 'error') {
    return (
      <button
        onClick={(e) => { e.stopPropagation(); startProcessing() }}
        className="text-xs px-2 py-0.5 rounded hover:opacity-80 transition-opacity"
        style={{ background: 'rgba(220,38,38,0.1)', color: '#dc2626' }}
      >
        Retry
      </button>
    )
  }

  // idle + pending — show Process button
  return (
    <button
      onClick={(e) => { e.stopPropagation(); startProcessing() }}
      className="text-xs px-2 py-0.5 rounded hover:opacity-80 transition-opacity"
      style={{ background: 'var(--brand-light)', color: 'var(--brand-coral)' }}
    >
      Process
    </button>
  )
}

// ---------------------------------------------------------------------------
// MeetingCard
// ---------------------------------------------------------------------------

interface MeetingCardProps {
  meeting: MeetingListItem
}

export function MeetingCard({ meeting }: MeetingCardProps) {
  const navigate = useNavigate()
  const status = meeting.processing_status
  const statusCfg = STATUS_CONFIG[status]
  const StatusIcon = statusCfg.icon
  const typeCfg = meeting.meeting_type ? TYPE_COLORS[meeting.meeting_type] : null
  const attendeeCount = meeting.attendees?.length ?? 0
  const tldr = meeting.summary?.tldr

  const variant = status === 'failed' ? 'action' : status === 'complete' ? 'complete' : 'info'

  return (
    <BrandedCard
      variant={variant}
      hoverable
      onClick={() => navigate(`/meetings/${meeting.id}`)}
    >
      {/* Header row: title + status */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3
          className="text-sm font-semibold leading-snug flex-1 min-w-0 truncate"
          style={{ color: 'var(--heading-text)' }}
        >
          {meeting.title ?? 'Untitled meeting'}
        </h3>
        <span
          className="flex items-center gap-1 shrink-0 text-xs"
          style={{ color: statusCfg.color }}
        >
          <StatusIcon className={`size-3${statusCfg.spin ? ' animate-spin' : ''}`} />
          {statusCfg.label}
        </span>
      </div>

      {/* Meta row: date, type badge, attendees */}
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <span className="text-xs" style={{ color: 'var(--secondary-text)' }}>
          {formatRelativeDate(meeting.meeting_date)}
        </span>
        {meeting.meeting_type && typeCfg && (
          <span
            className="text-xs px-1.5 py-0.5 rounded-full"
            style={{ background: typeCfg.bg, color: typeCfg.text }}
          >
            {formatMeetingType(meeting.meeting_type)}
          </span>
        )}
        {attendeeCount > 0 && (
          <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--secondary-text)' }}>
            <Users className="size-3" />
            {attendeeCount} attendee{attendeeCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* TLDR snippet if available */}
      {tldr && (
        <p
          className="text-xs line-clamp-2 mb-2"
          style={{ color: 'var(--secondary-text)' }}
        >
          {tldr}
        </p>
      )}

      {/* Process button for pending meetings */}
      {(status === 'pending' || status === 'failed') && (
        <div className="mt-1">
          <ProcessButton meetingId={meeting.id} status={status} />
        </div>
      )}

      {/* Calendar source badge for scheduled meetings */}
      {status === 'scheduled' && (
        <div className="mt-1">
          <span className="text-xs flex items-center gap-1" style={{ color: '#3B82F6' }}>
            <CalendarDays className="size-3" />
            Calendar
          </span>
        </div>
      )}
    </BrandedCard>
  )
}
