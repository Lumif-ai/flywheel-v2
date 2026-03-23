import type { StreamEntry } from '@/types/streams'
import { GrowthChart } from './GrowthChart'

interface StreamTimelineProps {
  entries: StreamEntry[]
  streamId?: string
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now()
  const date = new Date(dateStr).getTime()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60_000)
  const diffHr = Math.floor(diffMs / 3_600_000)
  const diffDay = Math.floor(diffMs / 86_400_000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay < 30) return `${diffDay}d ago`
  return new Date(dateStr).toLocaleDateString()
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength).trimEnd() + '...'
}

export function StreamTimeline({ entries, streamId }: StreamTimelineProps) {
  if (entries.length === 0) {
    return (
      <div className="space-y-6">
        {streamId && <GrowthChart streamId={streamId} />}
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <p className="text-sm text-muted-foreground">
            No activity yet. Context entries will appear here as you work.
          </p>
        </div>
      </div>
    )
  }

  const sorted = [...entries].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  return (
    <div className="space-y-3">
      {streamId && (
        <>
          <GrowthChart streamId={streamId} />
          <hr className="my-6 border-border" />
        </>
      )}
      {sorted.map((entry) => (
        <div
          key={entry.id}
          className="flex gap-3 rounded-lg border p-3"
        >
          <div className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-muted-foreground/40" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-medium">
                {entry.source}
              </span>
              <span className="text-xs text-muted-foreground">
                {formatRelativeTime(entry.created_at)}
              </span>
            </div>
            <p className="mt-1 text-sm text-foreground/80">
              {truncate(entry.content, 200)}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
