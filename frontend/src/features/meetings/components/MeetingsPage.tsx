import { useState } from 'react'
import { CalendarDays, Loader2, RefreshCw, Eye, EyeOff, X, Repeat } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { useMeetings } from '../hooks/useMeetings'
import { useSyncMeetings } from '../hooks/useSyncMeetings'
import { hideMeeting, queryKeys } from '../api'
import { MeetingCard } from './MeetingCard'
import type { MeetingListItem } from '../types/meetings'

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
// Time period grouping
// ---------------------------------------------------------------------------

interface TimeGroup {
  label: string
  meetings: MeetingListItem[]
}

function groupByTimePeriod(meetings: MeetingListItem[], tab: TimeTab): TimeGroup[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const tomorrow = new Date(today.getTime() + 86400000)
  const dayAfterTomorrow = new Date(today.getTime() + 2 * 86400000)
  const yesterday = new Date(today.getTime() - 86400000)

  // Find start of this week (Monday)
  const dayOfWeek = now.getDay()
  const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek
  const thisWeekStart = new Date(today.getTime() + mondayOffset * 86400000)
  const nextWeekStart = new Date(thisWeekStart.getTime() + 7 * 86400000)
  const nextWeekEnd = new Date(nextWeekStart.getTime() + 7 * 86400000)
  const lastWeekStart = new Date(thisWeekStart.getTime() - 7 * 86400000)

  const groups: Record<string, MeetingListItem[]> = {}
  const groupOrder: string[] = []

  function addToGroup(label: string, meeting: MeetingListItem) {
    if (!groups[label]) {
      groups[label] = []
      groupOrder.push(label)
    }
    groups[label].push(meeting)
  }

  for (const m of meetings) {
    const d = m.meeting_date ? new Date(m.meeting_date) : null
    if (!d) { addToGroup('Unknown', m); continue }

    if (tab === 'upcoming') {
      if (d >= today && d < tomorrow) addToGroup('Today', m)
      else if (d >= tomorrow && d < dayAfterTomorrow) addToGroup('Tomorrow', m)
      else if (d >= dayAfterTomorrow && d < nextWeekStart) addToGroup('This Week', m)
      else if (d >= nextWeekStart && d < nextWeekEnd) addToGroup('Next Week', m)
      else addToGroup('Later', m)
    } else {
      if (d >= yesterday && d < today) addToGroup('Yesterday', m)
      else if (d >= thisWeekStart && d < yesterday) addToGroup('Earlier This Week', m)
      else if (d >= lastWeekStart && d < thisWeekStart) addToGroup('Last Week', m)
      else addToGroup('Earlier', m)
    }
  }

  return groupOrder.map((label) => ({ label, meetings: groups[label] }))
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
  const [showHidden, setShowHidden] = useState(false)
  const [peopleFilter, setPeopleFilter] = useState<'all' | 'external' | 'internal'>('external')
  const { data: meetings, isLoading } = useMeetings({ time: activeTab, show_hidden: showHidden })
  const syncMutation = useSyncMeetings()
  const queryClient = useQueryClient()

  const hideMutation = useMutation({
    mutationFn: (id: string) => hideMeeting(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
    },
  })

  // Filter by internal/external attendees
  const filteredMeetings = (meetings ?? []).filter((m) => {
    if (peopleFilter === 'all') return true
    const attendees = m.attendees ?? []
    const hasExternal = attendees.some((a) => a.is_external)
    if (peopleFilter === 'external') return hasExternal
    return !hasExternal // internal = no external attendees
  })
  const displayMeetings = filteredMeetings
  const groups = groupByTimePeriod(displayMeetings, activeTab)

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

        {/* Time-based tabs + people filter + show hidden toggle */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1">
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

            {/* People filter */}
            <div className="h-5 w-px" style={{ background: 'var(--subtle-border)' }} />
            <div className="flex items-center gap-1">
              {(['all', 'external', 'internal'] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setPeopleFilter(filter)}
                  className="text-xs px-2.5 py-1 rounded-md font-medium transition-colors"
                  style={
                    peopleFilter === filter
                      ? { background: 'var(--brand-light)', color: 'var(--brand-coral)' }
                      : { color: 'var(--secondary-text)' }
                  }
                >
                  {filter === 'all' ? 'All' : filter === 'external' ? 'External' : 'Internal'}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() => setShowHidden(!showHidden)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors"
            style={{
              color: showHidden ? 'var(--brand-coral)' : 'var(--secondary-text)',
              background: showHidden ? 'rgba(233,77,53,0.06)' : 'transparent',
            }}
          >
            {showHidden ? <Eye className="size-3.5" /> : <EyeOff className="size-3.5" />}
            {showHidden ? 'Showing hidden' : 'Show hidden'}
          </button>
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
          <div className="space-y-8">
            {groups.map((group) => (
              <div key={group.label}>
                <h2
                  className="text-sm font-semibold mb-3 uppercase tracking-wide"
                  style={{ color: 'var(--secondary-text)' }}
                >
                  {group.label}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {group.meetings.map((meeting) => (
                    <div key={meeting.id} className="relative group">
                      <MeetingCard meeting={meeting} />
                      {/* Hide button overlay */}
                      {!meeting.hidden && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            hideMutation.mutate(meeting.id)
                          }}
                          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-black/5"
                          title={meeting.recurring_event_id ? 'Hide this recurring series' : 'Hide this meeting'}
                        >
                          {meeting.recurring_event_id ? (
                            <Repeat className="size-3.5" style={{ color: 'var(--secondary-text)' }} />
                          ) : (
                            <X className="size-3.5" style={{ color: 'var(--secondary-text)' }} />
                          )}
                        </button>
                      )}
                      {/* Hidden indicator */}
                      {meeting.hidden && (
                        <div
                          className="absolute inset-0 rounded-xl flex items-center justify-center"
                          style={{ background: 'rgba(255,255,255,0.7)' }}
                        >
                          <span className="text-xs font-medium" style={{ color: 'var(--secondary-text)' }}>
                            Hidden
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
