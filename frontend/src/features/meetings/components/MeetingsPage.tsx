import { useState } from 'react'
import { CalendarDays, Loader2, RefreshCw } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { useMeetings } from '../hooks/useMeetings'
import { useSyncMeetings } from '../hooks/useSyncMeetings'
import { MeetingCard } from './MeetingCard'
import type { ProcessingStatus } from '../types/meetings'

// ---------------------------------------------------------------------------
// Status filter options
// ---------------------------------------------------------------------------

type FilterTab = 'all' | ProcessingStatus

const FILTER_TABS: Array<{ key: FilterTab; label: string }> = [
  { key: 'all',      label: 'All' },
  { key: 'pending',  label: 'Pending' },
  { key: 'complete', label: 'Complete' },
  { key: 'skipped',  label: 'Skipped' },
  { key: 'failed',   label: 'Failed' },
]

// ---------------------------------------------------------------------------
// Skeleton loading cards
// ---------------------------------------------------------------------------

function MeetingSkeleton() {
  return (
    <div className="bg-[var(--card-bg)] border border-[var(--subtle-border)] rounded-xl p-6 space-y-3">
      <div className="flex justify-between">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-16" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-24" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-3/4" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// MeetingsPage
// ---------------------------------------------------------------------------

export function MeetingsPage() {
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all')
  const { data: meetings, isLoading } = useMeetings()
  const syncMutation = useSyncMeetings()

  // Sort by meeting_date desc (most recent first), filter by status
  const filteredMeetings = (meetings ?? [])
    .filter((m) => activeFilter === 'all' || m.processing_status === activeFilter)
    .sort((a, b) => {
      if (!a.meeting_date) return 1
      if (!b.meeting_date) return -1
      return new Date(b.meeting_date).getTime() - new Date(a.meeting_date).getTime()
    })

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: 'var(--page-bg)' }}>
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Page header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1
              className="text-2xl font-bold"
              style={{ color: 'var(--heading-text)' }}
            >
              Meetings
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--secondary-text)' }}>
              Your meeting intelligence hub
            </p>
          </div>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg font-medium transition-opacity hover:opacity-80 disabled:opacity-60"
            style={{
              background: 'var(--brand-coral)',
              color: '#fff',
            }}
          >
            {syncMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            Sync
          </button>
        </div>

        {/* Status filter tabs */}
        <div className="flex items-center gap-1 mb-6 flex-wrap">
          {FILTER_TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveFilter(key)}
              className="text-sm px-3 py-1.5 rounded-lg font-medium transition-colors"
              style={
                activeFilter === key
                  ? { background: 'var(--brand-coral)', color: '#fff' }
                  : { background: 'var(--card-bg)', color: 'var(--secondary-text)', border: '1px solid var(--subtle-border)' }
              }
            >
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <MeetingSkeleton />
            <MeetingSkeleton />
            <MeetingSkeleton />
          </div>
        ) : filteredMeetings.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title="No meetings yet"
            description={
              activeFilter !== 'all'
                ? `No ${activeFilter} meetings found. Try a different filter.`
                : "Connect Granola in Settings to sync your meetings"
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredMeetings.map((meeting) => (
              <MeetingCard key={meeting.id} meeting={meeting} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
