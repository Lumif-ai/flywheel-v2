import { useState, useMemo } from 'react'
import { NavLink, useNavigate } from 'react-router'
import { format } from 'date-fns'
import { BrandedCard } from '@/components/ui/branded-card'
import { Skeleton } from '@/components/ui/skeleton'
import { typography, colors, spacing } from '@/lib/design-tokens'
import type { MeetingItem } from '@/features/briefing/types/briefing-v2'

type MeetingFilter = 'external' | 'all'

interface TodaySectionProps {
  meetings: MeetingItem[] | undefined
  isLoading: boolean
  hasCalendar?: boolean
}

/**
 * TodaySection shows the founder's meetings for the day as compact cards
 * with attendee info and a one-click prep button.
 *
 * Three states: loading skeleton, empty (no meetings / no calendar), loaded cards.
 */
export function TodaySection({ meetings, isLoading, hasCalendar }: TodaySectionProps) {
  const [filter, setFilter] = useState<MeetingFilter>('external')
  const isLoadingState = isLoading || meetings === undefined

  const hasInternal = useMemo(
    () => meetings?.some((m) => m.is_internal) ?? false,
    [meetings],
  )

  const filtered = useMemo(() => {
    if (!meetings) return []
    if (filter === 'all') return meetings
    return meetings.filter((m) => !m.is_internal)
  }, [meetings, filter])

  // Empty state: not loading but no meetings
  if (!isLoadingState && meetings.length === 0) {
    return (
      <BrandedCard hoverable={false}>
        <h2
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            lineHeight: typography.sectionTitle.lineHeight,
            color: colors.headingText,
            margin: 0,
            marginBottom: spacing.element,
          }}
        >
          Today
        </h2>
        <p
          style={{
            fontSize: typography.caption.size,
            lineHeight: typography.caption.lineHeight,
            color: colors.secondaryText,
            margin: 0,
          }}
        >
          {hasCalendar
            ? 'No meetings scheduled for today.'
            : <>No meetings today.{' '}
                <NavLink
                  to="/settings/integrations"
                  style={{
                    color: colors.brandCoral,
                    textDecoration: 'none',
                    fontWeight: 500,
                  }}
                >
                  Connect your calendar
                </NavLink>{' '}
                to see upcoming calls.</>
          }
        </p>
      </BrandedCard>
    )
  }

  // Loading state: skeleton rows
  if (isLoadingState) {
    return (
      <BrandedCard hoverable={false}>
        <h2
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            lineHeight: typography.sectionTitle.lineHeight,
            color: colors.headingText,
            margin: 0,
            marginBottom: spacing.element,
          }}
        >
          Today
        </h2>
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </BrandedCard>
    )
  }

  // Loaded state: meeting cards
  return (
    <BrandedCard hoverable={false}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.element }}>
        <h2
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            lineHeight: typography.sectionTitle.lineHeight,
            color: colors.headingText,
            margin: 0,
          }}
        >
          Today
        </h2>

        {/* Internal / External toggle — only show when there are internal meetings */}
        {hasInternal && (
          <div
            style={{
              display: 'inline-flex',
              borderRadius: '8px',
              border: `1px solid ${colors.subtleBorder}`,
              overflow: 'hidden',
            }}
          >
            {(['external', 'all'] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                style={{
                  fontSize: '12px',
                  fontWeight: filter === value ? 600 : 400,
                  padding: '4px 12px',
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: filter === value ? colors.brandCoral : 'transparent',
                  color: filter === value ? '#fff' : colors.secondaryText,
                  transition: 'all 0.15s ease',
                }}
              >
                {value === 'external' ? 'External' : 'All'}
              </button>
            ))}
          </div>
        )}
      </div>
      <div>
        {filtered.length === 0 ? (
          <p style={{ fontSize: '13px', color: colors.secondaryText, margin: 0 }}>
            No external meetings today.
          </p>
        ) : (
          filtered.map((meeting, index) => (
            <MeetingCard
              key={meeting.id}
              meeting={meeting}
              isLast={index === filtered.length - 1}
            />
          ))
        )}
      </div>
    </BrandedCard>
  )
}

// ---------------------------------------------------------------------------
// MeetingCard — single meeting row with title, subtitle, and prep button
// ---------------------------------------------------------------------------

function MeetingCard({ meeting, isLast }: { meeting: MeetingItem; isLast: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingTop: '12px',
        paddingBottom: '12px',
        borderBottom: isLast ? 'none' : `1px solid ${colors.subtleBorder}`,
      }}
    >
      {/* Left side: title + subtitle */}
      <div style={{ flex: '1 1 0%', minWidth: 0 }}>
        <div
          style={{
            fontSize: '15px',
            fontWeight: 500,
            color: colors.headingText,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {meeting.title || 'Untitled meeting'}
        </div>
        <MeetingSubtitle meeting={meeting} />
      </div>

      {/* Right side: prep button */}
      <div style={{ marginLeft: '12px', flexShrink: 0 }}>
        <PrepButton meeting={meeting} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MeetingSubtitle — formatted time, company, attendees
// ---------------------------------------------------------------------------

function MeetingSubtitle({ meeting }: { meeting: MeetingItem }) {
  const parts: string[] = []

  // Time
  try {
    parts.push(format(new Date(meeting.time), 'h:mm a'))
  } catch {
    // If time parsing fails, skip it
  }

  // Company
  if (meeting.company) {
    parts.push(meeting.company)
  }

  // Attendees
  const attendeeNames = (meeting.attendees || [])
    .map(
      (a) =>
        (a as Record<string, string>).name ||
        (a as Record<string, string>).displayName ||
        (a as Record<string, string>).email ||
        'Unknown',
    )
    .slice(0, 3)

  const totalAttendees = (meeting.attendees || []).length
  if (attendeeNames.length > 0) {
    const nameStr = attendeeNames.join(', ')
    parts.push(totalAttendees > 3 ? `${nameStr} +${totalAttendees - 3} more` : nameStr)
  }

  if (parts.length === 0) return null

  return (
    <div
      style={{
        fontSize: '13px',
        color: colors.secondaryText,
        marginTop: '2px',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {parts.join(' \u00B7 ')}
    </div>
  )
}

// ---------------------------------------------------------------------------
// PrepButton — "View Prep" (coral) when available, "Prep" (outlined) otherwise
// ---------------------------------------------------------------------------

function PrepButton({ meeting }: { meeting: MeetingItem }) {
  const navigate = useNavigate()

  if (meeting.prep_status === 'available') {
    return (
      <NavLink
        to={`/documents?meeting_id=${meeting.id}`}
        style={{
          display: 'inline-block',
          fontSize: '13px',
          padding: '6px 12px',
          borderRadius: '8px',
          backgroundColor: '#E94D35',
          color: '#fff',
          textDecoration: 'none',
          fontWeight: 500,
          lineHeight: '1',
        }}
      >
        View Prep
      </NavLink>
    )
  }

  return (
    <button
      type="button"
      onClick={() =>
        navigate('/chat', {
          state: { prefill: `Prepare me for my meeting: ${meeting.title}` },
        })
      }
      style={{
        fontSize: '13px',
        padding: '6px 12px',
        borderRadius: '8px',
        border: `1px solid ${colors.subtleBorder}`,
        backgroundColor: 'transparent',
        color: colors.headingText,
        cursor: 'pointer',
        fontWeight: 500,
        lineHeight: '1',
      }}
    >
      Prep
    </button>
  )
}
