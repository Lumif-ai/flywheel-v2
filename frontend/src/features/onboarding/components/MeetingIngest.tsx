/**
 * MeetingIngest - Meeting notes paste/upload UI with batch processing,
 * stream auto-assignment display, and density jump visualization.
 *
 * Consumes useOnboarding hook for createdStreams (stream name display),
 * skipToBriefing, and goToBriefing phase transitions.
 */

import { useState, useRef } from 'react'
import {
  Video,
  Mic,
  FileText,
  Upload,
  X,
  Plus,
  CheckCircle,
  Loader2,
} from 'lucide-react'
import { useOnboarding } from '../hooks/useOnboarding'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NoteItem {
  id: string
  title: string
  preview: string
  content: string
}

interface DensityJump {
  stream_name: string
  before: number
  after: number
}

interface IngestResult {
  notes_processed: number
  entries_created: number
  stream_assignments: string[]
  density_jumps: DensityJump[]
}

// ---------------------------------------------------------------------------
// Platform grid (visual only for v3.0)
// ---------------------------------------------------------------------------

const PLATFORMS = [
  { name: 'Granola', icon: FileText },
  { name: 'Fireflies', icon: Mic },
  { name: 'Fathom', icon: Mic },
  { name: 'Otter', icon: Mic },
  { name: 'Zoom', icon: Video },
  { name: 'Teams', icon: Video },
  { name: 'Circleback', icon: FileText },
] as const

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface MeetingIngestProps {
  onComplete?: () => void
  onSkip?: () => void
}

export function MeetingIngest({ onComplete, onSkip }: MeetingIngestProps = {}) {
  const { createdStreams, skipToBriefing, goToBriefing } = useOnboarding()

  // Allow parent to override callbacks (used by TeamOnboarding)
  const handleComplete = onComplete ?? (() => goToBriefing())
  const handleSkip = onSkip ?? skipToBriefing

  // Local state
  const [notes, setNotes] = useState<NoteItem[]>([])
  const [pasteValue, setPasteValue] = useState('')
  const [processing, setProcessing] = useState(false)
  const [processedIndex, setProcessedIndex] = useState(0)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [platformToast, setPlatformToast] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ------------------------------------------------------------------
  // Add note from paste
  // ------------------------------------------------------------------
  const addPastedNote = () => {
    if (!pasteValue.trim()) return
    const firstLine = pasteValue.trim().split('\n')[0].slice(0, 80)
    const preview = pasteValue.trim().slice(0, 100)
    setNotes(prev => [
      ...prev,
      {
        id: crypto.randomUUID(),
        title: firstLine || 'Untitled Note',
        preview,
        content: pasteValue.trim(),
      },
    ])
    setPasteValue('')
  }

  // ------------------------------------------------------------------
  // Add notes from file upload
  // ------------------------------------------------------------------
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    for (const file of Array.from(files)) {
      const text = await file.text()
      const preview = text.slice(0, 100)
      setNotes(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          title: file.name.replace(/\.(txt|md)$/, ''),
          preview,
          content: text,
        },
      ])
    }

    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // ------------------------------------------------------------------
  // Remove a note
  // ------------------------------------------------------------------
  const removeNote = (id: string) => {
    setNotes(prev => prev.filter(n => n.id !== id))
  }

  // ------------------------------------------------------------------
  // Process notes via API
  // ------------------------------------------------------------------
  const processNotes = async () => {
    if (notes.length === 0) return

    setProcessing(true)
    setProcessedIndex(0)
    setResult(null)

    try {
      // Simulate per-note progress for UX feedback
      const progressInterval = setInterval(() => {
        setProcessedIndex(prev => Math.min(prev + 1, notes.length))
      }, 500)

      const res = await api.post('/onboarding/ingest-meetings', {
        notes: notes.map(n => ({ title: n.title, content: n.content })),
      })

      clearInterval(progressInterval)
      setProcessedIndex(notes.length)

      const data = res as Record<string, unknown>
      // Map stream IDs to names using createdStreams from hook
      const streamNames = ((data.stream_assignments as string[]) ?? []).map((id: string) => {
        const match = createdStreams.find(s => s.id === id)
        return match?.name ?? id
      })

      setResult({
        notes_processed: (data.notes_processed as number) ?? notes.length,
        entries_created: (data.entries_created as number) ?? 0,
        stream_assignments: streamNames,
        density_jumps: (data.density_jumps as DensityJump[]) ?? [],
      })
    } catch (err) {
      console.error('Meeting ingest failed:', err)
    } finally {
      setProcessing(false)
    }
  }

  // ------------------------------------------------------------------
  // Platform click handler (coming soon toast)
  // ------------------------------------------------------------------
  const handlePlatformClick = (name: string) => {
    setPlatformToast(name)
    setTimeout(() => setPlatformToast(null), 2500)
  }

  // ------------------------------------------------------------------
  // Render: results state
  // ------------------------------------------------------------------
  if (result) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="text-center space-y-2">
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto" />
          <h2 className="text-2xl font-semibold">
            Processed {result.notes_processed} notes
          </h2>
          <p className="text-muted-foreground">
            Created {result.entries_created} context entries
          </p>
        </div>

        {/* Stream assignments */}
        {result.stream_assignments.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Assigned to:</p>
            <div className="flex flex-wrap gap-2">
              {result.stream_assignments.map((name, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary/10 text-primary"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Density jump visualization */}
        {result.density_jumps.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm font-medium">Density improvements:</p>
            {result.density_jumps.map((jump, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span>{jump.stream_name}</span>
                  <span className="text-muted-foreground">
                    {jump.before} &rarr; {jump.after}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-1000 ease-out"
                    style={{ width: `${Math.min(jump.after, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={handleComplete}
          className="w-full py-3 px-4 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Continue to your briefing
        </button>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render: processing state
  // ------------------------------------------------------------------
  if (processing) {
    return (
      <div className="max-w-2xl mx-auto text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
        <p className="text-lg font-medium">
          Processing note {Math.min(processedIndex + 1, notes.length)} of{' '}
          {notes.length}...
        </p>
        <div className="h-2 rounded-full bg-muted overflow-hidden max-w-md mx-auto">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300"
            style={{ width: `${(processedIndex / notes.length) * 100}%` }}
          />
        </div>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render: input state
  // ------------------------------------------------------------------
  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Heading */}
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-semibold">
          Boost your workspace with meeting notes
        </h2>
        <p className="text-muted-foreground">
          Connect a meeting notes platform or paste notes directly
        </p>
      </div>

      {/* Platform grid */}
      <div className="relative">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {PLATFORMS.map(({ name, icon: Icon }) => (
            <button
              key={name}
              onClick={() => handlePlatformClick(name)}
              className="flex items-center gap-2 rounded-lg border p-3 hover:border-primary cursor-pointer opacity-60 hover:opacity-80 transition-all"
            >
              <Icon className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm">{name}</span>
            </button>
          ))}
        </div>

        {/* Coming soon toast */}
        {platformToast && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-background border rounded-lg shadow-lg px-4 py-2 text-sm animate-in fade-in zoom-in">
            Coming soon &mdash; use paste or upload below for now
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-sm text-muted-foreground">or add manually</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* Paste textarea */}
      <div className="space-y-3">
        <textarea
          value={pasteValue}
          onChange={e => setPasteValue(e.target.value)}
          rows={6}
          placeholder="Paste your meeting notes here..."
          className="w-full rounded-lg border bg-background px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
        />

        <div className="flex items-center gap-3">
          <button
            onClick={addPastedNote}
            disabled={!pasteValue.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            Add note
          </button>

          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm hover:bg-muted/50 transition-colors"
          >
            <Upload className="w-4 h-4" />
            Or upload files
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md"
            multiple
            onChange={handleFileUpload}
            className="hidden"
          />
        </div>
      </div>

      {/* Notes list */}
      {notes.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">{notes.length} note(s) added</p>
          {notes.map(note => (
            <div
              key={note.id}
              className="flex items-start gap-3 rounded-lg border p-3"
            >
              <FileText className="w-4 h-4 mt-0.5 text-muted-foreground flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{note.title}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {note.preview}
                </p>
              </div>
              <button
                onClick={() => removeNote(note.id)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}

          <button
            onClick={() => setPasteValue('')}
            className="flex items-center gap-1 text-sm text-primary hover:underline"
          >
            <Plus className="w-3 h-3" />
            Add more notes
          </button>
        </div>
      )}

      {/* Process button */}
      {notes.length > 0 && (
        <button
          onClick={processNotes}
          className="w-full py-3 px-4 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Process {notes.length} note{notes.length !== 1 ? 's' : ''}
        </button>
      )}

      {/* Skip */}
      <div className="text-center">
        <button
          onClick={handleSkip}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Skip for now
        </button>
      </div>
    </div>
  )
}
