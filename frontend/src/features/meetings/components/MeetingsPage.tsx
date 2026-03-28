import { useState } from 'react'
import { CalendarDays, Loader2, RefreshCw } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { useMeetings } from '../hooks/useMeetings'
import { useSyncMeetings } from '../hooks/useSyncMeetings'
import { MeetingCard } from './MeetingCard'

// ---------------------------------------------------------------------------
// Time-based tabs
// ---------------------------------------------------------------------------

type TimeTab = 'upcoming' | 'past'

const TIME_TABS: Array<{ key: TimeTab; label: string }> = [
  { key: 'upcoming', label: 'Upcoming' },
  { key: 'past',     label: 'Past' },
]

const EMPTY_DESCRIPTIONS: Record<TimeTab, string> = {
  upcoming: 'No upcoming meetings. Connect Google Calendar in Settings to sync your schedule.',
  past: 'No past meetings found.',
}

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
  const [activeTab, setActiveTab] = useState<TimeTab>('upcoming')
  const { data: meetings, isLoading } = useMeetings({ time: activeTab })
  const syncMutation = useSyncMeetings()

  const displayMeetings = meetings ?? []

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
              Calendar events and meeting notes in one place
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

        {/* Time-based tabs */}
        <div className="flex items-center gap-1 mb-6 flex-wrap">
          {TIME_TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className="text-sm px-3 py-1.5 rounded-lg font-medium transition-colors"
              style={
                activeTab === key
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
        ) : displayMeetings.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title="No meetings"
            description={EMPTY_DESCRIPTIONS[activeTab]}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {displayMeetings.map((meeting) => (
              <MeetingCard key={meeting.id} meeting={meeting} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
