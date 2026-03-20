import { useState, useMemo } from 'react'
import { Search, Database } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useContextFiles } from '../hooks/useContextFiles'
import { formatRelativeTime } from '@/features/history/components/utils'

interface FileListProps {
  selectedFile: string | null
  onSelectFile: (fileName: string) => void
}

function stripExtension(name: string): string {
  return name.replace(/\.md$/, '')
}

export function FileList({ selectedFile, onSelectFile }: FileListProps) {
  const { data: files, isLoading, isError } = useContextFiles()
  const [search, setSearch] = useState('')

  const filteredFiles = useMemo(() => {
    if (!files) return []
    if (!search) return files
    const lower = search.toLowerCase()
    return files.filter((f) => f.file_name.toLowerCase().includes(lower))
  }, [files, search])

  if (isLoading) {
    return (
      <div className="space-y-2 p-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="space-y-1.5 rounded-lg border p-3">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-6 text-center">
        <p className="text-sm text-destructive">Failed to load context files</p>
      </div>
    )
  }

  if (!files || files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 p-8 text-center">
        <Database className="size-8 text-muted-foreground/50" />
        <p className="text-sm font-medium text-foreground">No context files yet</p>
        <p className="text-xs text-muted-foreground">
          Context files are created as skills accumulate knowledge
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter files..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-1 px-3 pb-3">
          {filteredFiles.map((file) => (
            <button
              key={file.file_name}
              onClick={() => onSelectFile(file.file_name)}
              className={`w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/50 ${
                selectedFile === file.file_name
                  ? 'border-primary/30 bg-primary/5'
                  : ''
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-foreground truncate">
                  {stripExtension(file.file_name)}
                </span>
                <Badge variant="secondary" className="shrink-0">
                  {file.entry_count}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Updated {formatRelativeTime(file.last_updated)}
              </p>
            </button>
          ))}

          {filteredFiles.length === 0 && search && (
            <p className="py-4 text-center text-xs text-muted-foreground">
              No files match &quot;{search}&quot;
            </p>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
