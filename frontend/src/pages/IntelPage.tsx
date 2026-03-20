import { useState, useMemo } from 'react'
import { FileList } from '@/features/intel/components/FileList'
import { EntryDetail } from '@/features/intel/components/EntryDetail'
import { useContextFiles } from '@/features/intel/hooks/useContextFiles'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { Database } from 'lucide-react'

export function IntelPage() {
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const isDesktop = useMediaQuery('(min-width: 768px)')
  const { data: files } = useContextFiles()

  const stats = useMemo(() => {
    if (!files) return null
    const totalFiles = files.length
    const totalEntries = files.reduce((sum, f) => sum + f.entry_count, 0)
    return { totalFiles, totalEntries }
  }, [files])

  // Mobile: show either file list or entry detail
  if (!isDesktop) {
    if (selectedFile) {
      return (
        <div className="flex h-[calc(100vh-8rem)] flex-col">
          <EntryDetail
            fileName={selectedFile}
            onBack={() => setSelectedFile(null)}
            showBackButton
          />
        </div>
      )
    }

    return (
      <div className="flex h-[calc(100vh-8rem)] flex-col">
        <div className="p-6 pb-0 space-y-1">
          <h1 className="text-2xl font-bold text-foreground">Intel</h1>
          <p className="text-muted-foreground">Context store browser</p>
          {stats && (
            <div className="flex items-center gap-3 pt-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Database className="size-3" />
                {stats.totalFiles} files
              </span>
              <span>{stats.totalEntries} entries</span>
            </div>
          )}
        </div>
        <FileList selectedFile={selectedFile} onSelectFile={setSelectedFile} />
      </div>
    )
  }

  // Desktop: two-column layout
  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col p-6">
      <div className="mb-4 space-y-1">
        <h1 className="text-2xl font-bold text-foreground">Intel</h1>
        <div className="flex items-center gap-4">
          <p className="text-muted-foreground">Context store browser</p>
          {stats && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Database className="size-3" />
                {stats.totalFiles} files
              </span>
              <span>{stats.totalEntries} entries</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* Left panel: file list (~1/3) */}
        <div className="w-1/3 min-w-[240px] max-w-[360px] rounded-xl border">
          <FileList selectedFile={selectedFile} onSelectFile={setSelectedFile} />
        </div>

        {/* Right panel: entry detail (~2/3) */}
        <div className="flex-1 rounded-xl border">
          <EntryDetail fileName={selectedFile} />
        </div>
      </div>
    </div>
  )
}
