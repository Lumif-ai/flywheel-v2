import { useMemo, useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { colors, typography } from '@/lib/design-tokens'
import { useEmailStore } from '../store/emailStore'
import { ThreadCard } from './ThreadCard'
import type { Thread, FlatItem, PriorityTier } from '../types/email'

interface ThreadListProps {
  threads: Thread[]
  loading: boolean
}

const TIER_ORDER: PriorityTier[] = ['critical', 'high', 'medium', 'low', 'unscored']

const TIER_LABELS: Record<PriorityTier, string> = {
  critical: 'Critical Priority',
  high: 'High Priority',
  medium: 'Medium Priority',
  low: 'Low Priority',
  unscored: 'Unscored',
}

function buildFlatItems(threads: Thread[]): FlatItem[] {
  const items: FlatItem[] = []
  let lastTier: PriorityTier | null = null

  // Sort threads by tier order, then by latest_received_at desc within tier
  const sorted = [...threads].sort((a, b) => {
    const tierDiff = TIER_ORDER.indexOf(a.priority_tier) - TIER_ORDER.indexOf(b.priority_tier)
    if (tierDiff !== 0) return tierDiff
    return new Date(b.latest_received_at).getTime() - new Date(a.latest_received_at).getTime()
  })

  for (const thread of sorted) {
    if (thread.priority_tier !== lastTier) {
      items.push({ type: 'header', tier: thread.priority_tier, label: TIER_LABELS[thread.priority_tier] })
      lastTier = thread.priority_tier
    }
    items.push({ type: 'thread', thread })
  }

  return items
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-2 p-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="h-20 rounded-xl animate-pulse"
          style={{ backgroundColor: 'var(--subtle-border)' }}
        />
      ))}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
        No threads found
      </p>
      <p style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
        Sync your email to get started
      </p>
    </div>
  )
}

export function ThreadList({ threads, loading }: ThreadListProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  const { selectedThreadId, selectThread } = useEmailStore()

  const flatItems = useMemo(() => buildFlatItems(threads), [threads])

  const virtualizer = useVirtualizer({
    count: flatItems.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => (flatItems[index].type === 'header' ? 40 : 84),
    overscan: 5,
  })

  if (loading) return <LoadingSkeleton />
  if (threads.length === 0) return <EmptyState />

  const virtualItems = virtualizer.getVirtualItems()

  return (
    <div
      ref={parentRef}
      className="overflow-auto flex-1"
      style={{ height: '100%' }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            transform: `translateY(${virtualItems[0]?.start ?? 0}px)`,
          }}
        >
          {virtualItems.map((virtualRow) => {
            const item = flatItems[virtualRow.index]

            if (item.type === 'header') {
              return (
                <div
                  key={`header-${item.tier}`}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                  className="px-4 py-2"
                  style={{
                    backgroundColor: 'var(--page-bg)',
                    position: 'sticky',
                    top: 0,
                    zIndex: 1,
                  }}
                >
                  <span
                    style={{
                      fontSize: typography.caption.size,
                      fontWeight: '600',
                      color: colors.secondaryText,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}
                  >
                    {item.label}
                  </span>
                </div>
              )
            }

            return (
              <div
                key={item.thread.thread_id}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                className="px-4 py-1"
              >
                <ThreadCard
                  thread={item.thread}
                  isSelected={selectedThreadId === item.thread.thread_id}
                  onSelect={selectThread}
                />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
