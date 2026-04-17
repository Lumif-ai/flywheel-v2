import { useRef, useState } from 'react'
import { Download, FileText, Upload } from 'lucide-react'
import { format } from 'date-fns'
import { useDocumentUpload } from '../hooks/useDocumentUpload'
import { RunInClaudeCodeButton } from './shared/RunInClaudeCodeButton'
import { useAuthStore } from '@/stores/auth'

interface DocumentEntry {
  file_id?: string
  name?: string
  type?: string
  mimetype?: string
  size?: number
  uploaded_at?: string
}

interface DocumentUploadZoneProps {
  projectId: string
  documents: DocumentEntry[]
}

function getIconColor(mime?: string): string {
  if (!mime) return '#6B7280'
  if (mime === 'application/pdf') return '#DC2626'
  if (
    mime === 'application/vnd.ms-excel' ||
    mime === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  )
    return '#16A34A'
  if (
    mime === 'application/msword' ||
    mime === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  )
    return '#2563EB'
  return '#6B7280'
}

function formatSize(bytes?: number): string {
  if (!bytes) return ''
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} B`
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return ''
  try {
    return format(new Date(dateStr), 'MMM d')
  } catch {
    return ''
  }
}

export function DocumentUploadZone({ projectId, documents }: DocumentUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const { mutate: upload, isPending } = useDocumentUpload(projectId)

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    upload(Array.from(files))
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = () => {
    setIsDragOver(false)
  }

  const handleClick = () => {
    inputRef.current?.click()
  }

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        className={`relative border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors ${
          isDragOver
            ? 'border-[#E94D35] bg-[rgba(233,77,53,0.05)]'
            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
        }`}
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        {isPending ? (
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <svg
              className="animate-spin h-6 w-6"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0" strokeOpacity="0.25" />
              <path d="M21 12a9 9 0 0 0-9-9" />
            </svg>
            <p className="text-sm">Uploading...</p>
          </div>
        ) : (
          <>
            <Upload className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground text-center">
              Drop files here or click to upload
            </p>
            <p className="text-xs text-muted-foreground/70">
              PDF, Word, Excel, CSV, TXT, PNG, JPG
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="*"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* File cards */}
      {documents.length > 0 && (
        <div className="space-y-2">
          {documents.map((doc, idx) => {
            const mime = doc.mimetype ?? doc.type
            const iconColor = getIconColor(mime)
            return (
              <div
                key={doc.name ?? idx}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${doc.file_id ? 'cursor-pointer hover:bg-gray-50 transition-colors' : ''}`}
                onClick={async () => {
                  if (!doc.file_id) return
                  try {
                    const token = useAuthStore.getState().token
                    const res = await fetch(`/api/v1/files/${doc.file_id}/download`, {
                      headers: token ? { Authorization: `Bearer ${token}` } : {},
                    })
                    if (res.ok) {
                      const data = await res.json()
                      if (data.download_url) window.open(data.download_url, '_blank')
                    }
                  } catch {
                    // silent
                  }
                }}
              >
                <FileText className="h-4 w-4 flex-shrink-0" style={{ color: iconColor }} />
                <span className="text-sm font-medium truncate flex-1">
                  {doc.name ?? 'Untitled'}
                </span>
                {doc.size != null && (
                  <span className="text-xs text-muted-foreground flex-shrink-0">
                    {formatSize(doc.size)}
                  </span>
                )}
                {doc.uploaded_at && (
                  <span className="text-xs text-muted-foreground flex-shrink-0">
                    {formatDate(doc.uploaded_at)}
                  </span>
                )}
                {doc.file_id && (
                  <Download className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Run in Claude Code button — shown after first upload */}
      {documents.length > 0 && (
        <div className="pt-1">
          <RunInClaudeCodeButton
            command="/broker:process-project"
            label="Analyze Documents with Claude"
            variant="prominent"
          />
        </div>
      )}
    </div>
  )
}
