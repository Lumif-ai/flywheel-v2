import { useState, useRef, useEffect } from 'react'
import type { WorkStreamEntity, SubThread } from '@/types/streams'
import { DensityBar, DensityDot } from './DensityIndicator'
import { useCreateSubThread } from '../hooks/useStreamDetail'
import { ChevronRight, Plus } from 'lucide-react'
import { cn } from '@/lib/cn'

function getSubThreadPlaceholder(streamName: string): string {
  const lower = streamName.toLowerCase()
  if (lower.includes('hiring') || lower.includes('recruit')) {
    return 'e.g., Senior Engineer role'
  }
  if (lower.includes('pipeline') || lower.includes('sales') || lower.includes('deal')) {
    return 'e.g., Acme Corp deal'
  }
  if (lower.includes('fund') || lower.includes('invest')) {
    return 'e.g., Sequoia round'
  }
  return 'e.g., New sub-thread'
}

interface StreamIntelligenceProps {
  streamId: string
  streamName: string
  entities: WorkStreamEntity[]
  densityScore: number
  subThreads: SubThread[]
}

export function StreamIntelligence({
  streamId,
  streamName,
  entities,
  densityScore,
  subThreads,
}: StreamIntelligenceProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [showAddInput, setShowAddInput] = useState(false)
  const [newName, setNewName] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const createSubThread = useCreateSubThread(streamId)

  useEffect(() => {
    if (showAddInput && inputRef.current) {
      inputRef.current.focus()
    }
  }, [showAddInput])

  function toggleExpanded(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function handleSubmit() {
    const trimmed = newName.trim()
    if (!trimmed) return
    createSubThread.mutate(
      { name: trimmed },
      {
        onSuccess: () => {
          setNewName('')
          setShowAddInput(false)
        },
      }
    )
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    } else if (e.key === 'Escape') {
      setNewName('')
      setShowAddInput(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Knowledge Coverage */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-muted-foreground">
          Knowledge Coverage
        </h3>
        <DensityBar score={densityScore} showLabel />
      </div>

      {/* Sub-threads */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-medium text-muted-foreground">
            Sub-threads
          </h3>
          <button
            onClick={() => setShowAddInput(true)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            <Plus className="h-3 w-3" />
            Add
          </button>
        </div>

        {/* Inline add input */}
        {showAddInput && (
          <div className="mb-3">
            <input
              ref={inputRef}
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={() => {
                if (!newName.trim()) {
                  setShowAddInput(false)
                }
              }}
              placeholder={getSubThreadPlaceholder(streamName)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={createSubThread.isPending}
            />
          </div>
        )}

        {subThreads.length === 0 && !showAddInput ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <p className="text-sm text-muted-foreground">
              No sub-threads yet. Add one to organize nested work.
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {subThreads.map((thread) => {
              const isExpanded = expandedIds.has(thread.id)
              return (
                <div key={thread.id} className="rounded-lg border bg-background">
                  <button
                    onClick={() => toggleExpanded(thread.id)}
                    className="flex w-full items-center justify-between px-3 py-2.5 text-left hover:bg-muted/50 transition-colors rounded-lg"
                  >
                    <div className="flex items-center gap-2">
                      <ChevronRight
                        className={cn(
                          'h-4 w-4 text-muted-foreground transition-transform duration-200',
                          isExpanded && 'rotate-90'
                        )}
                      />
                      <span className="text-sm font-medium">{thread.name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <DensityDot score={thread.density_score} />
                      <span className="text-xs text-muted-foreground">
                        {thread.entry_count} {thread.entry_count === 1 ? 'entry' : 'entries'}
                      </span>
                    </div>
                  </button>
                  <div
                    className={cn(
                      'overflow-hidden transition-all duration-200',
                      isExpanded ? 'max-h-40' : 'max-h-0'
                    )}
                  >
                    <div className="px-3 pb-3 pt-0 pl-9 text-xs text-muted-foreground">
                      Sub-thread detail view coming in Phase 36
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Linked Entities */}
      <div>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">
          Linked Entities
        </h3>

        {entities.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <p className="text-sm text-muted-foreground">
              No entities linked. Intelligence will appear as context accumulates.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {entities.map((entity) => (
              <div
                key={entity.id}
                className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5"
              >
                <span className="text-sm font-medium">{entity.entity_name}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(entity.linked_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
