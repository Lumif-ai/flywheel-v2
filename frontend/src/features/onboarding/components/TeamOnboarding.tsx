/**
 * TeamOnboarding - Two-step flow for invited team members.
 *
 * Step 1 (streams phase): Show team's existing streams as checkbox cards,
 * allow selecting which to join, and add new stream names.
 *
 * Step 2 (meetings phase): Reuse MeetingIngest component for meeting notes.
 */

import { useState } from 'react'
import { Users, Plus, Loader2 } from 'lucide-react'
import { MeetingIngest } from './MeetingIngest'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TeamStream {
  id: string
  name: string
  entity_count: number
  entry_count: number
  member_count: number
}

interface TeamOnboardingProps {
  phase: 'streams' | 'meetings'
  tenantName: string | null
  teamStreams: TeamStream[]
  selectedStreamIds: Set<string>
  newStreamNames: string[]
  loading: boolean
  toggleStream: (id: string) => void
  addNewStream: (name: string) => void
  confirmStreams: () => void
  skipStreams: () => void
  skipMeetings: () => void
  onMeetingsComplete: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TeamOnboarding({
  phase,
  tenantName,
  teamStreams,
  selectedStreamIds,
  newStreamNames,
  loading,
  toggleStream,
  addNewStream,
  confirmStreams,
  skipStreams,
  skipMeetings,
  onMeetingsComplete,
}: TeamOnboardingProps) {
  const [newStreamInput, setNewStreamInput] = useState('')

  const handleAddStream = () => {
    if (!newStreamInput.trim()) return
    addNewStream(newStreamInput.trim())
    setNewStreamInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddStream()
    }
  }

  // -----------------------------------------------------------------------
  // Step 2: Meetings phase
  // -----------------------------------------------------------------------
  if (phase === 'meetings') {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-semibold">Add your perspective</h2>
          <p className="text-muted-foreground">
            Connect your meeting notes to add context the team doesn&apos;t have yet
          </p>
        </div>

        <MeetingIngest
          onComplete={onMeetingsComplete}
          onSkip={skipMeetings}
        />
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Step 1: Streams phase
  // -----------------------------------------------------------------------
  const totalSelected = selectedStreamIds.size + newStreamNames.length

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-semibold">
          Welcome to {tenantName ?? 'your team'}!
        </h2>
        <p className="text-muted-foreground">
          Your team is already tracking these work streams. Select the ones you&apos;re
          involved in.
        </p>
      </div>

      {/* Team stream cards */}
      {teamStreams.length > 0 && (
        <div className="space-y-2">
          {teamStreams.map(stream => {
            const isSelected = selectedStreamIds.has(stream.id)
            return (
              <button
                key={stream.id}
                onClick={() => toggleStream(stream.id)}
                className={`w-full flex items-start gap-3 rounded-xl border p-4 text-left transition-colors ${
                  isSelected
                    ? 'border-primary bg-primary/5'
                    : 'border-border bg-card hover:bg-accent/50'
                }`}
              >
                <div
                  className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded border transition-colors ${
                    isSelected
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-muted-foreground/30'
                  }`}
                >
                  {isSelected && (
                    <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M2 6l3 3 5-5"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium">{stream.name}</p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{stream.entity_count} entities</span>
                    <span>{stream.entry_count} entries</span>
                    <span className="inline-flex items-center gap-1">
                      <Users className="h-3 w-3" />
                      {stream.member_count} members
                    </span>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* New stream names already added */}
      {newStreamNames.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            New streams you suggested:
          </p>
          <div className="flex flex-wrap gap-2">
            {newStreamNames.map((name, i) => (
              <span
                key={i}
                className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Add new stream input */}
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          Add something your team isn&apos;t tracking yet
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={newStreamInput}
            onChange={e => setNewStreamInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g., Acme Corp renewal..."
            className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
          <button
            onClick={handleAddStream}
            disabled={!newStreamInput.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium hover:bg-muted/50 disabled:opacity-50 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        </div>
      </div>

      {/* Continue / Skip */}
      <div className="space-y-3">
        <button
          onClick={confirmStreams}
          disabled={loading || totalSelected === 0}
          className="w-full py-3 px-4 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin mx-auto" />
          ) : (
            `Continue${totalSelected > 0 ? ` with ${totalSelected} stream${totalSelected !== 1 ? 's' : ''}` : ''}`
          )}
        </button>
        <div className="text-center">
          <button
            onClick={skipStreams}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  )
}
