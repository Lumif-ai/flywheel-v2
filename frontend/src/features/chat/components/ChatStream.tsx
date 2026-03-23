import { useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { useSSE } from '@/lib/sse'
import { api } from '@/lib/api'
import { useChatStore } from '../store'
import type { SSEEvent } from '@/types/events'

interface ChatStreamProps {
  runId: string
}

export function ChatStream({ runId }: ChatStreamProps) {
  const streamState = useChatStore((s) => s.streamState)
  const setStreamStatus = useChatStore((s) => s.setStreamStatus)
  const appendChunk = useChatStore((s) => s.appendChunk)
  const setStreamOutput = useChatStore((s) => s.setStreamOutput)
  const setStreamError = useChatStore((s) => s.setStreamError)
  const queryClient = useQueryClient()

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.type) {
        case 'thinking':
          setStreamStatus('thinking')
          break
        case 'text':
          appendChunk(event.data.content as string)
          break
        case 'skill_start':
          setStreamStatus('running')
          break
        case 'stage': {
          // Stage events from skill_executor: started, executing, rendering
          const stage = event.data.stage as string
          if (stage === 'started' || stage === 'executing' || stage === 'rendering') {
            setStreamStatus('running')
          }
          break
        }
        case 'result':
          // Result event carries rendered_html from completed run
          setStreamOutput((event.data.rendered_html as string) ?? '')
          break
        case 'done': {
          const html = event.data.rendered_html as string | undefined
          if (html) {
            setStreamOutput(html)
          } else {
            // Fallback: fetch run detail if rendered_html not in SSE event
            api.get<{ rendered_html?: string }>(`/skills/runs/${runId}`)
              .then((res) => setStreamOutput(res.rendered_html ?? ''))
              .catch(() => setStreamOutput(''))
          }
          // Invalidate streams to pick up density changes from context writes
          queryClient.invalidateQueries({ queryKey: ['streams'] })
          break
        }
        case 'error':
          setStreamError((event.data.message as string) ?? 'Unknown error')
          break
      }
    },
    [setStreamStatus, appendChunk, setStreamOutput, setStreamError, queryClient],
  )

  useSSE(
    streamState.status !== 'complete' && streamState.status !== 'error'
      ? `/api/v1/skills/runs/${runId}/stream`
      : null,
    handleEvent,
  )

  if (streamState.status === 'thinking') {
    return (
      <div className="flex items-center gap-2 py-2">
        <Skeleton className="h-4 w-4 rounded-full" />
        <span className="text-sm text-muted-foreground animate-pulse">
          Thinking...
        </span>
      </div>
    )
  }

  if (streamState.status === 'streaming' || streamState.status === 'running') {
    return (
      <div className="py-2">
        {streamState.status === 'running' && (
          <Badge variant="secondary" className="mb-2 animate-pulse">
            Running skill...
          </Badge>
        )}
        <p className="text-sm text-foreground whitespace-pre-wrap">
          {streamState.chunks.join('')}
        </p>
      </div>
    )
  }

  if (streamState.status === 'error') {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span>{streamState.error ?? 'Something went wrong'}</span>
      </div>
    )
  }

  return null
}
