import { useState } from 'react'
import {
  Mail,
  MessageSquare,
  Calendar,
  FileText,
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
} from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import type { TimelineItem } from '../../types/relationships'

interface TimelineTabProps {
  timeline: TimelineItem[]
}

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)
  const diffWeek = Math.floor(diffDay / 7)
  const diffMonth = Math.floor(diffDay / 30)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  if (diffWeek < 5) return `${diffWeek}w ago`
  if (diffMonth < 12) return `${diffMonth}mo ago`
  return `${Math.floor(diffMonth / 12)}y ago`
}

function sourceIcon(source: string) {
  const src = source.toLowerCase()
  if (src === 'email') return Mail
  if (src === 'note') return MessageSquare
  if (src === 'meeting') return Calendar
  if (src === 'document') return FileText
  return Activity
}

function TimelineEntry({ entry }: { entry: TimelineItem }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = sourceIcon(entry.source)
  const isInbound = entry.direction === 'inbound'
  const isOutbound = entry.direction === 'outbound'
  const dateToUse = entry.date || entry.created_at

  return (
    <div
      className="flex gap-3 py-3 border-b border-[var(--subtle-border)] last:border-b-0 cursor-pointer group"
      onClick={() => setExpanded((prev) => !prev)}
    >
      {/* Icon */}
      <div
        className="mt-0.5 shrink-0 flex items-center justify-center size-7 rounded-full"
        style={{ background: 'var(--brand-tint)', color: 'var(--brand-coral)' }}
      >
        <Icon className="size-3.5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            {/* Direction indicator */}
            {isInbound && (
              <ArrowDownLeft
                className="size-3.5 shrink-0"
                style={{ color: 'var(--secondary-text)' }}
              />
            )}
            {isOutbound && (
              <ArrowUpRight
                className="size-3.5 shrink-0"
                style={{ color: 'var(--secondary-text)' }}
              />
            )}

            {/* Content/title */}
            <span
              className="text-sm font-medium truncate"
              style={{ color: 'var(--heading-text)' }}
            >
              {entry.content}
            </span>
          </div>

          {/* Time ago */}
          <span
            className="text-xs shrink-0"
            style={{ color: 'var(--secondary-text)' }}
          >
            {timeAgo(dateToUse)}
          </span>
        </div>

        {/* Contact name */}
        {entry.contact_name && (
          <p
            className="text-xs mt-0.5"
            style={{ color: 'var(--secondary-text)' }}
          >
            {entry.contact_name}
          </p>
        )}

        {/* Expanded content */}
        {expanded && entry.content && (
          <p
            className="text-sm mt-2 leading-relaxed"
            style={{ color: 'var(--body-text)' }}
          >
            {entry.content}
          </p>
        )}
      </div>
    </div>
  )
}

const INITIAL_LIMIT = 10

export function TimelineTab({ timeline }: TimelineTabProps) {
  const [showAll, setShowAll] = useState(false)

  if (timeline.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No timeline entries yet"
        description="Activities like emails, meetings, and notes will appear here as they are captured."
      />
    )
  }

  const visible = showAll ? timeline : timeline.slice(0, INITIAL_LIMIT)

  return (
    <div>
      <div className="divide-y-0">
        {visible.map((entry) => (
          <TimelineEntry key={entry.id} entry={entry} />
        ))}
      </div>

      {!showAll && timeline.length > INITIAL_LIMIT && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-3 text-sm font-medium transition-opacity hover:opacity-70"
          style={{ color: 'var(--brand-coral)' }}
        >
          Show {timeline.length - INITIAL_LIMIT} more entries
        </button>
      )}
    </div>
  )
}
