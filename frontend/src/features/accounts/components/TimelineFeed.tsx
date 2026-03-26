import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { typography } from '@/lib/design-tokens'
import { Send, FileText } from 'lucide-react'
import { useTimeline } from '../hooks/useTimeline'
import type { TimelineItem } from '../types/accounts'

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function channelColor(channel: string | null): string {
  switch (channel?.toLowerCase()) {
    case 'email':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
    case 'linkedin':
      return 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300'
    case 'phone':
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
  }
}

interface TimelineItemRowProps {
  item: TimelineItem
}

function TimelineItemRow({ item }: TimelineItemRowProps) {
  const isOutreach = item.type === 'outreach'

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-b-0">
      <div
        className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full ${
          isOutreach
            ? 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400'
            : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
        }`}
      >
        {isOutreach ? <Send className="size-3.5" /> : <FileText className="size-3.5" />}
      </div>

      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-foreground">{item.title}</p>
        {item.summary && (
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
            {item.summary}
          </p>
        )}
        <p
          className="text-muted-foreground mt-1"
          style={{ fontSize: typography.caption.size }}
        >
          {formatDate(item.date)}
        </p>
      </div>

      <div className="flex flex-col items-end gap-1 shrink-0">
        {item.status && (
          <Badge variant="secondary" className="text-[10px]">
            {item.status}
          </Badge>
        )}
        {item.channel && (
          <span
            className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${channelColor(item.channel)}`}
          >
            {item.channel}
          </span>
        )}
        {item.confidence && (
          <Badge variant="outline" className="text-[10px]">
            {item.confidence}
          </Badge>
        )}
      </div>
    </div>
  )
}

interface TimelineFeedProps {
  accountId: string
  initialTimeline: TimelineItem[]
}

export function TimelineFeed({ accountId, initialTimeline }: TimelineFeedProps) {
  const [offset, setOffset] = useState(0)
  const limit = 20
  const [usePaginated, setUsePaginated] = useState(false)

  const { data, isLoading } = useTimeline(accountId, { offset, limit })

  const hasMore = usePaginated ? (data?.has_more ?? false) : initialTimeline.length >= limit

  function handleLoadMore() {
    if (!usePaginated) {
      setUsePaginated(true)
      setOffset(initialTimeline.length)
    } else {
      setOffset((prev) => prev + limit)
    }
  }

  // Merge initial + paginated items when switching to paginated mode
  const displayItems = usePaginated
    ? [...initialTimeline, ...(data?.items ?? [])]
    : initialTimeline

  return (
    <div>
      <h2
        className="text-foreground mb-4"
        style={{
          fontSize: typography.sectionTitle.size,
          fontWeight: typography.sectionTitle.weight,
          lineHeight: typography.sectionTitle.lineHeight,
        }}
      >
        Timeline
      </h2>

      {displayItems.length === 0 ? (
        <p className="text-muted-foreground text-sm">No activity yet</p>
      ) : (
        <div>
          {displayItems.map((item) => (
            <TimelineItemRow key={item.id} item={item} />
          ))}
        </div>
      )}

      {hasMore && (
        <div className="mt-4 flex justify-center">
          <Button
            variant="outline"
            size="sm"
            onClick={handleLoadMore}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Load more'}
          </Button>
        </div>
      )}
    </div>
  )
}
