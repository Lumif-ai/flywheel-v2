import { useState, useCallback, useRef, useEffect } from 'react'
import { Search, ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useContextEntries, type EntryFilters } from '../hooks/useContextEntries'
import { formatRelativeTime } from '@/features/history/components/utils'

const CONFIDENCE_VARIANT: Record<string, 'default' | 'secondary' | 'outline'> = {
  high: 'default',
  medium: 'secondary',
  low: 'outline',
}

const VISIBILITY_VARIANT: Record<string, 'default' | 'secondary' | 'outline'> = {
  public: 'default',
  tenant: 'secondary',
  private: 'outline',
}

const PAGE_SIZE = 20

interface EntryDetailProps {
  fileName: string | null
  onBack?: () => void
  showBackButton?: boolean
}

function EntryContent({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false)
  const lines = content.split('\n')
  const isTruncatable = lines.length > 3

  return (
    <div className="mt-2 text-sm text-foreground/80">
      <p className="whitespace-pre-wrap">
        {expanded || !isTruncatable ? content : lines.slice(0, 3).join('\n') + '...'}
      </p>
      {isTruncatable && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            setExpanded(!expanded)
          }}
          className="mt-1 text-xs font-medium text-primary hover:underline"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </div>
  )
}

export function EntryDetail({ fileName, onBack, showBackButton }: EntryDetailProps) {
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [offset, setOffset] = useState(0)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  const filters: EntryFilters | null = fileName
    ? { file_name: fileName, search: searchTerm || undefined, offset, limit: PAGE_SIZE }
    : null

  const { data, isLoading, isError } = useContextEntries(filters)

  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSearchTerm(value)
      setOffset(0)
    }, 300)
  }, [])

  useEffect(() => {
    return () => clearTimeout(debounceRef.current)
  }, [])

  // Reset when file changes
  useEffect(() => {
    setSearchInput('')
    setSearchTerm('')
    setOffset(0)
  }, [fileName])

  // No file selected placeholder
  if (!fileName) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <FileText className="size-12 opacity-30" />
        <p className="text-sm">Select a file to view entries</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="space-y-2 border-b p-3">
        <div className="flex items-center gap-2">
          {showBackButton && onBack && (
            <Button variant="ghost" size="icon-sm" onClick={onBack}>
              <ChevronLeft className="size-4" />
            </Button>
          )}
          <h2 className="text-sm font-semibold text-foreground truncate">
            {fileName.replace(/\.md$/, '')}
          </h2>
          {data && (
            <Badge variant="secondary" className="shrink-0">
              {data.total} entries
            </Badge>
          )}
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search entries..."
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      {/* Entry list */}
      {isLoading && !data && (
        <div className="space-y-3 p-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2 rounded-xl border p-4">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          ))}
        </div>
      )}

      {isError && (
        <div className="p-6 text-center">
          <p className="text-sm text-destructive">Failed to load entries</p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 p-8">
          <p className="text-sm text-muted-foreground">No entries found</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <ScrollArea className="flex-1">
            <div className="space-y-2 p-3">
              {data.items.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded-xl border p-4 space-y-1"
                >
                  {/* Header row */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-sm font-medium text-foreground">
                      {entry.source}
                    </span>
                    {entry.detail && (
                      <>
                        <span className="text-muted-foreground">|</span>
                        <span className="text-sm text-muted-foreground">
                          {entry.detail}
                        </span>
                      </>
                    )}
                  </div>

                  {/* Badges row */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant={CONFIDENCE_VARIANT[entry.confidence] ?? 'outline'}>
                      {entry.confidence}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {entry.evidence} {entry.evidence === 1 ? 'source' : 'sources'}
                    </span>
                    {entry.visibility && (
                      <Badge variant={VISIBILITY_VARIANT[entry.visibility] ?? 'outline'}>
                        {entry.visibility}
                      </Badge>
                    )}
                  </div>

                  {/* Content */}
                  <EntryContent content={entry.content} />

                  {/* Timestamp */}
                  <p className="text-xs text-muted-foreground">
                    {formatRelativeTime(entry.created_at)}
                  </p>
                </div>
              ))}
            </div>
          </ScrollArea>

          {/* Pagination */}
          {data.total > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t p-3">
              <p className="text-xs text-muted-foreground">
                Showing {offset + 1}-{Math.min(offset + PAGE_SIZE, data.total)} of{' '}
                {data.total}
              </p>
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={!data.has_more}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
