import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { colors, typography } from '@/lib/design-tokens'
import { useEmailStore } from '../store/emailStore'
import { useThreadDetail } from '../hooks/useThreadDetail'
import { DraftReview } from './DraftReview'
import type { Message, PriorityTier } from '../types/email'

const TIER_COLORS: Record<PriorityTier, string> = {
  critical: '#E94D35',
  high: '#F97316',
  medium: '#F59E0B',
  low: '#6B7280',
  unscored: '#9CA3AF',
}

function priorityToTier(priority: number): PriorityTier {
  if (priority >= 5) return 'critical'
  if (priority >= 4) return 'high'
  if (priority >= 3) return 'medium'
  return 'low'
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

function MessageRow({ message, isLatest }: { message: Message; isLatest: boolean }) {
  const [reasoningOpen, setReasoningOpen] = useState(isLatest)

  return (
    <div
      className="rounded-xl border p-4 flex flex-col gap-2"
      style={{ borderColor: 'var(--subtle-border)', backgroundColor: 'var(--card-bg)' }}
    >
      {/* Message header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col min-w-0">
          <span
            className="truncate"
            style={{
              fontSize: typography.body.size,
              fontWeight: '500',
              color: colors.headingText,
            }}
          >
            {message.sender_name || message.sender_email}
          </span>
          <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
            {message.sender_email}
          </span>
        </div>
        <span
          className="shrink-0"
          style={{ fontSize: typography.caption.size, color: colors.secondaryText }}
        >
          {formatRelativeTime(message.received_at)}
        </span>
      </div>

      {/* Snippet */}
      <p style={{ fontSize: typography.body.size, color: colors.secondaryText, margin: 0 }}>
        {message.snippet}
      </p>

      {/* Score section */}
      {message.score && (
        <div
          className="flex flex-col gap-2 rounded-lg p-3"
          style={{ backgroundColor: 'rgba(0,0,0,0.02)', border: '1px solid var(--subtle-border)' }}
        >
          <div className="flex items-center gap-2 flex-wrap">
            {/* Priority badge — color mapped to tier (red=critical, orange=high, amber=medium, gray=low) */}
            {(() => {
              const msgTier = priorityToTier(message.score.priority)
              return (
                <span
                  className="rounded-full px-2 py-0.5 text-xs font-medium"
                  style={{
                    color: TIER_COLORS[msgTier],
                    backgroundColor: `${TIER_COLORS[msgTier]}1A`,
                  }}
                >
                  P{message.score.priority}
                </span>
              )
            })()}
            {/* Category */}
            <span
              className="rounded-full px-2 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: 'rgba(59,130,246,0.1)',
                color: '#3B82F6',
              }}
            >
              {message.score.category}
            </span>
            {/* Suggested action */}
            {message.score.suggested_action && (
              <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
                {message.score.suggested_action}
              </span>
            )}
          </div>

          {/* Reasoning (collapsible) */}
          {message.score.reasoning && (
            <div>
              <button
                onClick={() => setReasoningOpen((o) => !o)}
                className="flex items-center gap-1 text-xs font-medium transition-opacity hover:opacity-70"
                style={{ color: colors.secondaryText }}
              >
                {reasoningOpen ? (
                  <ChevronDown className="size-3" />
                ) : (
                  <ChevronRight className="size-3" />
                )}
                Reasoning
              </button>
              {reasoningOpen && (
                <p
                  className="mt-1"
                  style={{
                    fontSize: typography.caption.size,
                    color: colors.secondaryText,
                    lineHeight: '1.5',
                  }}
                >
                  {message.score.reasoning}
                </p>
              )}
            </div>
          )}

          {/* Context refs */}
          {message.score.context_refs.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {message.score.context_refs.map((ref) => (
                <span
                  key={ref.entry_id}
                  className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                  style={{
                    backgroundColor: 'rgba(233,77,53,0.08)',
                    color: 'var(--brand-coral)',
                  }}
                  title={ref.content_preview}
                >
                  {ref.file_name ?? ref.entry_id.slice(0, 8)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-4">
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <div className="mt-4 flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    </div>
  )
}

export function ThreadDetail() {
  const { selectedThreadId, detailOpen, closeDetail } = useEmailStore()
  const { data, isLoading } = useThreadDetail(selectedThreadId)

  return (
    <Sheet open={detailOpen} onOpenChange={(open: boolean) => !open && closeDetail()}>
      <SheetContent side="right" className="w-[500px] sm:w-[540px] flex flex-col overflow-hidden p-0">
        {isLoading ? (
          <DetailSkeleton />
        ) : data ? (
          <>
            <SheetHeader className="border-b px-4 py-4 shrink-0" style={{ borderColor: 'var(--subtle-border)' }}>
              <div className="pr-8">
                <SheetTitle className="text-base font-semibold leading-snug">
                  {data.subject}
                </SheetTitle>
                {data.max_priority != null && (
                  <div className="mt-1.5 flex items-center gap-2">
                    <span
                      className="rounded-full px-2 py-0.5 text-xs font-medium"
                      style={{
                        color: TIER_COLORS[data.priority_tier],
                        backgroundColor: `${TIER_COLORS[data.priority_tier]}1A`,
                      }}
                    >
                      P{data.max_priority}
                    </span>
                    <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
                      {data.priority_tier}
                    </span>
                  </div>
                )}
              </div>
            </SheetHeader>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              {/* Messages */}
              <div className="flex flex-col gap-3">
                {data.messages.map((message: Message, idx: number) => (
                  <MessageRow
                    key={message.id}
                    message={message}
                    isLatest={idx === data.messages.length - 1}
                  />
                ))}
              </div>

              {/* Draft section */}
              {data.draft && (
                <div className="mt-4 pt-4 border-t" style={{ borderColor: 'var(--subtle-border)' }}>
                  <DraftReview draft={data.draft} />
                </div>
              )}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
