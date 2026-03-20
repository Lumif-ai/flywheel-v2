import { useEffect, useRef } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import type { CrawlEvent } from '../hooks/useCrawl'

interface CrawlStreamProps {
  events: CrawlEvent[]
}

export function CrawlStream({ events }: CrawlStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div className="mx-auto max-w-xl space-y-3">
      {events.map((event, i) => (
        <div
          key={i}
          className="flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300"
          style={{ animationDelay: `${i * 50}ms` }}
        >
          <span className="relative mt-1.5 flex h-2 w-2 shrink-0">
            {i === events.length - 1 ? (
              <>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
              </>
            ) : (
              <span className="inline-flex h-2 w-2 rounded-full bg-muted-foreground/40" />
            )}
          </span>
          <p className="text-sm text-foreground/80">{event.content}</p>
        </div>
      ))}

      {/* Skeleton placeholders for the profile being built */}
      <div className="mt-4 space-y-3 rounded-lg border border-border p-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <div className="grid grid-cols-2 gap-2 pt-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>

      <div ref={bottomRef} />
    </div>
  )
}
