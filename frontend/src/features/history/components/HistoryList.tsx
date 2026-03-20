import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ChevronLeft, ChevronRight, RotateCcw, Zap } from 'lucide-react'
import type { PaginatedResponse, SkillRun } from '@/types/api'
import { formatRelativeTime } from './utils'

const STATUS_VARIANT: Record<string, 'default' | 'destructive' | 'secondary' | 'outline'> = {
  completed: 'default',
  failed: 'destructive',
  running: 'secondary',
  pending: 'outline',
}

interface HistoryListProps {
  data: PaginatedResponse<SkillRun> | undefined
  isLoading: boolean
  isError: boolean
  error: Error | null
  offset: number
  limit: number
  onOffsetChange: (offset: number) => void
  onSelectRun: (id: string) => void
  selectedRunId: string | null
  refetch: () => void
}

export function HistoryList({
  data,
  isLoading,
  isError,
  error,
  offset,
  limit,
  onOffsetChange,
  onSelectRun,
  selectedRunId,
  refetch,
}: HistoryListProps) {
  // Loading state
  if (isLoading && !data) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border p-4 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-3 w-1/4" />
          </div>
        ))}
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-6 text-center space-y-3">
        <p className="text-sm text-destructive">
          {error?.message ?? 'Failed to load skill runs'}
        </p>
        <Button variant="outline" size="sm" onClick={refetch}>
          <RotateCcw className="size-3.5" data-icon="inline-start" />
          Retry
        </Button>
      </div>
    )
  }

  // Empty state
  if (!data || data.items.length === 0) {
    return (
      <div className="rounded-xl border p-8 text-center space-y-2">
        <Zap className="mx-auto size-8 text-muted-foreground/50" />
        <p className="text-sm font-medium text-foreground">No skill runs found</p>
        <p className="text-xs text-muted-foreground">
          Run a skill to see it appear here
        </p>
      </div>
    )
  }

  const showingStart = offset + 1
  const showingEnd = Math.min(offset + limit, data.total)

  return (
    <div className="space-y-3">
      {data.items.map((run) => (
        <button
          key={run.id}
          onClick={() => onSelectRun(run.id)}
          className={`w-full rounded-xl border p-4 text-left transition-colors hover:bg-muted/50 ${
            selectedRunId === run.id
              ? 'border-primary/30 bg-primary/5'
              : ''
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground truncate">
                  {run.skill_name}
                </span>
                <Badge
                  variant={STATUS_VARIANT[run.status] ?? 'outline'}
                  className={
                    run.status === 'running'
                      ? 'animate-pulse'
                      : ''
                  }
                >
                  {run.status}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatRelativeTime(run.created_at)}
              </p>
            </div>
            {run.tokens_used != null && (
              <span className="shrink-0 text-xs text-muted-foreground">
                {run.tokens_used.toLocaleString()} tokens
              </span>
            )}
          </div>
        </button>
      ))}

      {/* Pagination */}
      <div className="flex items-center justify-between pt-2">
        <p className="text-xs text-muted-foreground">
          Showing {showingStart}-{showingEnd} of {data.total}
        </p>
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            disabled={offset === 0}
            onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            disabled={!data.has_more}
            onClick={() => onOffsetChange(offset + limit)}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
