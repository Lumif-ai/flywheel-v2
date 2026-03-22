import { useState, useCallback, useRef, type KeyboardEvent } from 'react'
import { X, Plus, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import type { ParsedStream } from '../hooks/useOnboarding'

// ---------------------------------------------------------------------------
// Quick-pick options
// ---------------------------------------------------------------------------

const QUICK_PICKS = [
  'Sales Pipeline',
  'Hiring',
  'Fundraising',
  'Product Launch',
  'Client Projects',
  'Market Research',
]

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StreamCreatorProps {
  phase: 'stream_input' | 'stream_confirm'
  parsedStreams: ParsedStream[]
  loading: boolean
  error: string | null
  onParse: (input: string) => void
  onUpdate: (index: number, updates: Partial<ParsedStream>) => void
  onRemove: (index: number) => void
  onAdd: (name: string) => void
  onConfirm: () => void
}

// ---------------------------------------------------------------------------
// Stream Input Phase
// ---------------------------------------------------------------------------

function StreamInput({
  loading,
  error,
  onParse,
}: {
  loading: boolean
  error: string | null
  onParse: (input: string) => void
}) {
  const [value, setValue] = useState('')

  const handleQuickPick = useCallback((pick: string) => {
    setValue((prev) => {
      if (!prev.trim()) return pick
      // Append comma-separated
      return `${prev}, ${pick}`
    })
  }, [])

  const handleParse = useCallback(() => {
    if (value.trim()) {
      onParse(value.trim())
    }
  }, [value, onParse])

  return (
    <div className="w-full space-y-4 text-center">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">
          What's on your plate?
        </h2>
        <p className="text-muted-foreground">
          Tell us what you're working on and we'll organize your workspace
        </p>
      </div>

      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="I'm hiring engineers, closing the Acme deal, and planning our Series A..."
        rows={3}
        className="resize-none text-base"
        disabled={loading}
      />

      {/* Quick-pick buttons */}
      <div className="flex flex-wrap justify-center gap-2">
        {QUICK_PICKS.map((pick) => (
          <button
            key={pick}
            type="button"
            onClick={() => handleQuickPick(pick)}
            disabled={loading}
            className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
          >
            {pick}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Parse button */}
      <Button
        onClick={handleParse}
        disabled={loading || !value.trim()}
        size="lg"
        className="gap-2 px-8"
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Parsing your work streams...
          </>
        ) : (
          'Parse'
        )}
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Editable Stream Card
// ---------------------------------------------------------------------------

function StreamCard({
  stream,
  index,
  onUpdate,
  onRemove,
}: {
  stream: ParsedStream
  index: number
  onUpdate: (index: number, updates: Partial<ParsedStream>) => void
  onRemove: (index: number) => void
}) {
  const [editingName, setEditingName] = useState(false)
  const [nameValue, setNameValue] = useState(stream.name)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleNameClick = useCallback(() => {
    setEditingName(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }, [])

  const handleNameBlur = useCallback(() => {
    setEditingName(false)
    if (nameValue.trim() && nameValue.trim() !== stream.name) {
      onUpdate(index, { name: nameValue.trim() })
    } else {
      setNameValue(stream.name)
    }
  }, [nameValue, stream.name, index, onUpdate])

  const handleNameKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        inputRef.current?.blur()
      } else if (e.key === 'Escape') {
        setNameValue(stream.name)
        setEditingName(false)
      }
    },
    [stream.name],
  )

  return (
    <div className="group relative rounded-lg border border-border p-4 hover:border-primary transition-colors">
      {/* Remove button */}
      <button
        type="button"
        onClick={() => onRemove(index)}
        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
      >
        <X className="h-4 w-4" />
      </button>

      {/* Name (click to edit) */}
      {editingName ? (
        <input
          ref={inputRef}
          value={nameValue}
          onChange={(e) => setNameValue(e.target.value)}
          onBlur={handleNameBlur}
          onKeyDown={handleNameKeyDown}
          className="w-full bg-transparent text-base font-medium text-foreground outline-none border-b border-primary pb-0.5"
        />
      ) : (
        <button
          type="button"
          onClick={handleNameClick}
          className="text-left text-base font-medium text-foreground hover:text-primary transition-colors cursor-text"
        >
          {stream.name}
        </button>
      )}

      {/* Description */}
      {stream.description && (
        <p className="mt-1 text-sm text-muted-foreground">{stream.description}</p>
      )}

      {/* Entity seeds as badges */}
      {stream.entity_seeds.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {stream.entity_seeds.map((seed) => (
            <Badge key={seed} variant="secondary" className="text-xs">
              {seed}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Add Stream inline input
// ---------------------------------------------------------------------------

function AddStreamInput({ onAdd }: { onAdd: (name: string) => void }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleOpen = useCallback(() => {
    setOpen(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }, [])

  const handleSubmit = useCallback(() => {
    if (value.trim()) {
      onAdd(value.trim())
      setValue('')
      setOpen(false)
    }
  }, [value, onAdd])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        handleSubmit()
      } else if (e.key === 'Escape') {
        setValue('')
        setOpen(false)
      }
    },
    [handleSubmit],
  )

  if (!open) {
    return (
      <button
        type="button"
        onClick={handleOpen}
        className="flex items-center gap-2 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground hover:border-primary hover:text-primary transition-colors w-full"
      >
        <Plus className="h-4 w-4" />
        Add stream
      </button>
    )
  }

  return (
    <div className="flex gap-2 rounded-lg border border-primary p-3">
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Stream name..."
        className="flex-1 bg-transparent text-sm outline-none"
      />
      <Button onClick={handleSubmit} size="sm" disabled={!value.trim()}>
        Add
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Stream Confirm Phase
// ---------------------------------------------------------------------------

function StreamConfirm({
  parsedStreams,
  loading,
  onUpdate,
  onRemove,
  onAdd,
  onConfirm,
}: {
  parsedStreams: ParsedStream[]
  loading: boolean
  onUpdate: (index: number, updates: Partial<ParsedStream>) => void
  onRemove: (index: number) => void
  onAdd: (name: string) => void
  onConfirm: () => void
}) {
  return (
    <div className="w-full space-y-4">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">
          Here's what we found
        </h2>
        <p className="text-muted-foreground">
          {parsedStreams.length} work stream{parsedStreams.length !== 1 ? 's' : ''} detected.
          Click to rename, drag to reorder, or remove what doesn't fit.
        </p>
      </div>

      {/* Stream cards */}
      <div className="space-y-3">
        {parsedStreams.map((stream, i) => (
          <StreamCard
            key={`${stream.name}-${i}`}
            stream={stream}
            index={i}
            onUpdate={onUpdate}
            onRemove={onRemove}
          />
        ))}
        <AddStreamInput onAdd={onAdd} />
      </div>

      {/* Confirm button */}
      <div className="flex justify-center pt-2">
        <Button
          onClick={onConfirm}
          disabled={loading || parsedStreams.length === 0}
          size="lg"
          className="gap-2 px-8"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating workspace...
            </>
          ) : (
            'Create workspace'
          )}
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function StreamCreator({
  phase,
  parsedStreams,
  loading,
  error,
  onParse,
  onUpdate,
  onRemove,
  onAdd,
  onConfirm,
}: StreamCreatorProps) {
  if (phase === 'stream_input') {
    return <StreamInput loading={loading} error={error} onParse={onParse} />
  }

  return (
    <StreamConfirm
      parsedStreams={parsedStreams}
      loading={loading}
      onUpdate={onUpdate}
      onRemove={onRemove}
      onAdd={onAdd}
      onConfirm={onConfirm}
    />
  )
}
