import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { ChevronDown, ChevronRight, FileText, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { sanitizeHTML } from '@/lib/sanitize'
import { useSkillRun } from '../hooks/useHistory'
import { formatRelativeTime, formatDuration } from './utils'

const STATUS_VARIANT: Record<string, 'default' | 'destructive' | 'secondary' | 'outline'> = {
  completed: 'default',
  failed: 'destructive',
  running: 'secondary',
  pending: 'outline',
}

interface OutputViewerProps {
  runId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function OutputViewer({ runId, open, onOpenChange }: OutputViewerProps) {
  const { data: run, isLoading, isError, refetch } = useSkillRun(runId)
  const [paramsExpanded, setParamsExpanded] = useState(false)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        {isLoading && (
          <SheetHeader>
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </SheetHeader>
        )}

        {isError && (
          <div className="flex flex-col items-center justify-center gap-3 p-6">
            <p className="text-sm text-destructive">Failed to load run details</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RotateCcw className="size-3.5" data-icon="inline-start" />
              Retry
            </Button>
          </div>
        )}

        {run && (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <SheetTitle>{run.skill_name}</SheetTitle>
                <Badge
                  variant={STATUS_VARIANT[run.status] ?? 'outline'}
                  className={run.status === 'running' ? 'animate-pulse' : ''}
                >
                  {run.status}
                </Badge>
              </div>
              <SheetDescription>
                {formatRelativeTime(run.created_at)} &middot;{' '}
                {formatDuration(run.created_at, run.completed_at)}
              </SheetDescription>
            </SheetHeader>

            {/* Metadata row */}
            {(run.tokens_used != null || run.cost_estimate != null) && (
              <div className="flex gap-4 px-4 text-xs text-muted-foreground">
                {run.tokens_used != null && (
                  <span>{run.tokens_used.toLocaleString()} tokens</span>
                )}
                {run.cost_estimate != null && (
                  <span>${run.cost_estimate.toFixed(4)}</span>
                )}
              </div>
            )}

            {/* Input params (collapsible) */}
            {run.input_params && Object.keys(run.input_params).length > 0 && (
              <div className="px-4">
                <button
                  onClick={() => setParamsExpanded(!paramsExpanded)}
                  className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  {paramsExpanded ? (
                    <ChevronDown className="size-3" />
                  ) : (
                    <ChevronRight className="size-3" />
                  )}
                  Input parameters
                </button>
                {paramsExpanded && (
                  <pre className="mt-2 rounded-lg bg-muted/50 p-3 text-xs text-foreground overflow-x-auto">
                    {JSON.stringify(run.input_params, null, 2)}
                  </pre>
                )}
              </div>
            )}

            {/* Output */}
            <ScrollArea className="flex-1 px-4 pb-4">
              {run.output_html ? (
                <div
                  className="prose prose-sm prose-neutral dark:prose-invert max-w-none"
                  dangerouslySetInnerHTML={{
                    __html: sanitizeHTML(run.output_html),
                  }}
                />
              ) : (
                <div className="flex flex-col items-center justify-center gap-2 py-12 text-muted-foreground">
                  <FileText className="size-8 opacity-50" />
                  <p className="text-sm">No output available</p>
                </div>
              )}
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
