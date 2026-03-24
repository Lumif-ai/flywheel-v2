import { PenLine } from 'lucide-react'
import { cn } from '@/lib/cn'
import { colors, typography } from '@/lib/design-tokens'
import type { Thread, PriorityTier } from '../types/email'

interface ThreadCardProps {
  thread: Thread
  isSelected: boolean
  onSelect: (threadId: string) => void
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay}d ago`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const tierColors: Record<PriorityTier, string> = {
  critical: '#E94D35',
  high: '#F97316',
  medium: '#F59E0B',
  low: '#6B7280',
  unscored: '#9CA3AF',
}

function PriorityBadge({ priority, tier }: { priority: number | null; tier: PriorityTier }) {
  const color = tierColors[tier]
  const label = priority != null ? `P${priority}` : tier === 'unscored' ? '—' : `P?`
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        color,
        backgroundColor: `${color}1A`,
      }}
    >
      {label}
    </span>
  )
}

export function ThreadCard({ thread, isSelected, onSelect }: ThreadCardProps) {
  return (
    <div
      className={cn(
        'flex cursor-pointer flex-col gap-1 rounded-xl border px-4 py-3 transition-colors',
        isSelected
          ? 'border-[var(--brand-coral)] bg-[rgba(233,77,53,0.05)]'
          : 'border-[var(--subtle-border)] bg-[var(--card-bg)] hover:bg-[rgba(233,77,53,0.03)]',
      )}
      style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}
      onClick={() => onSelect(thread.thread_id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(thread.thread_id)
        }
      }}
    >
      {/* Row 1: sender + time + badges */}
      <div className="flex items-center gap-2">
        <span
          className="truncate flex-1"
          style={{
            fontSize: typography.body.size,
            fontWeight: thread.is_read ? '400' : '600',
            color: colors.headingText,
          }}
        >
          {thread.sender_name || thread.sender_email}
        </span>

        <div className="flex shrink-0 items-center gap-1.5">
          {thread.has_pending_draft && (
            <PenLine className="size-3.5" style={{ color: colors.brandCoral }} />
          )}
          {thread.message_count > 1 && (
            <span
              className="rounded-full px-1.5 py-0.5 text-xs"
              style={{
                backgroundColor: 'var(--subtle-border)',
                color: colors.secondaryText,
              }}
            >
              {thread.message_count}
            </span>
          )}
          <PriorityBadge priority={thread.max_priority} tier={thread.priority_tier} />
          <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
            {formatRelativeTime(thread.latest_received_at)}
          </span>
        </div>
      </div>

      {/* Row 2: subject */}
      <p
        className="truncate"
        style={{
          fontSize: typography.body.size,
          fontWeight: thread.is_read ? '400' : '500',
          color: thread.is_read ? colors.secondaryText : colors.headingText,
          margin: 0,
        }}
      >
        {thread.subject}
      </p>
    </div>
  )
}
