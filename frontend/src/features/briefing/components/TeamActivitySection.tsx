import { useState } from 'react'
import { Zap, Database, FileText, ChevronDown, ChevronRight } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import { Skeleton } from '@/components/ui/skeleton'
import { typography, colors, spacing } from '@/lib/design-tokens'
import type { TeamActivityGroup } from '@/features/briefing/types/briefing-v2'

interface TeamActivitySectionProps {
  activity: TeamActivityGroup[] | undefined
  isLoading: boolean
}

// ---------------------------------------------------------------------------
// Section title style (matches all other section h2 patterns)
// ---------------------------------------------------------------------------

const sectionTitleStyle: React.CSSProperties = {
  fontSize: typography.sectionTitle.size,
  fontWeight: typography.sectionTitle.weight,
  lineHeight: typography.sectionTitle.lineHeight,
  color: colors.headingText,
  margin: 0,
  marginBottom: spacing.element,
}

// ---------------------------------------------------------------------------
// Group label mapping — human-readable descriptions per group type
// ---------------------------------------------------------------------------

const GROUP_LABELS: Record<string, (count: number) => string> = {
  skill_runs: (n) => `Ran ${n} skill${n !== 1 ? 's' : ''}`,
  context_writes: (n) => `Saved ${n} piece${n !== 1 ? 's' : ''} of intelligence`,
  documents: (n) => `Created ${n} document${n !== 1 ? 's' : ''}`,
}

const GROUP_ICONS: Record<string, LucideIcon> = {
  skill_runs: Zap,
  context_writes: Database,
  documents: FileText,
}

// ---------------------------------------------------------------------------
// formatTimeAgo — local helper (copied pattern, PulseSignals being removed)
// ---------------------------------------------------------------------------

function formatTimeAgo(timestamp: string | undefined): string {
  if (!timestamp) return ''
  const now = Date.now()
  const then = new Date(timestamp).getTime()
  if (isNaN(then)) return ''
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHrs = Math.floor(diffMin / 60)
  if (diffHrs < 24) return `${diffHrs}h ago`
  const diffDays = Math.floor(diffHrs / 24)
  return `${diffDays}d ago`
}

// ---------------------------------------------------------------------------
// humanize — "meeting-processor" -> "Meeting processor"
// ---------------------------------------------------------------------------

function humanize(slug: string): string {
  const spaced = slug.replace(/-/g, ' ').replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

// ---------------------------------------------------------------------------
// getItemLabel — derive display label from item based on group type
// ---------------------------------------------------------------------------

function getItemLabel(item: Record<string, unknown>, groupType: string): string {
  switch (groupType) {
    case 'skill_runs': {
      const name = item.skill_name as string | undefined
      return name ? humanize(name) : 'Skill run'
    }
    case 'context_writes':
      return (item.file_name as string) || 'Context entry'
    case 'documents': {
      const title = (item.title as string) || 'Document'
      const docType = item.document_type as string | undefined
      return docType ? `${title} (${docType})` : title
    }
    default:
      return 'Activity'
  }
}

// ---------------------------------------------------------------------------
// ActivityItem — single item row within an expanded group
// ---------------------------------------------------------------------------

function ActivityItem({
  item,
  groupType,
}: {
  item: Record<string, unknown>
  groupType: string
}) {
  const label = getItemLabel(item, groupType)
  const timestamp = (item.created_at ?? item.timestamp ?? item.updated_at) as string | undefined

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingTop: '8px',
        paddingBottom: '8px',
      }}
    >
      <span
        style={{
          fontSize: typography.body.size,
          color: colors.bodyText,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          minWidth: 0,
        }}
      >
        {label}
      </span>
      {timestamp && (
        <span
          style={{
            fontSize: typography.caption.size,
            color: colors.secondaryText,
            flexShrink: 0,
            marginLeft: '12px',
          }}
        >
          {formatTimeAgo(timestamp)}
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ActivityGroupCard — collapsible group with header + item list
// ---------------------------------------------------------------------------

function ActivityGroupCard({
  group,
  isLast,
}: {
  group: TeamActivityGroup
  isLast: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  const Icon = GROUP_ICONS[group.type] || Zap
  const labelFn = GROUP_LABELS[group.type] || ((n: number) => `${group.type} (${n})`)
  const Chevron = expanded ? ChevronDown : ChevronRight

  return (
    <div
      style={{
        borderBottom: isLast ? 'none' : `1px solid ${colors.subtleBorder}`,
      }}
    >
      {/* Clickable header row */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((prev) => !prev)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setExpanded((prev) => !prev)
          }
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          width: '100%',
          paddingTop: '12px',
          paddingBottom: '12px',
          background: 'none',
          border: 'none',
          textAlign: 'left',
        }}
      >
        <Icon size={16} style={{ color: colors.secondaryText, flexShrink: 0 }} />
        <span
          style={{
            fontSize: '15px',
            fontWeight: 500,
            color: colors.headingText,
            flex: '1 1 0%',
          }}
        >
          {labelFn(group.count)}
        </span>
        <Chevron size={16} style={{ color: colors.secondaryText, flexShrink: 0 }} />
      </div>

      {/* Expanded items */}
      {expanded && group.items.length > 0 && (
        <div style={{ paddingLeft: '28px', paddingBottom: '8px' }}>
          {group.items.map((item, idx) => (
            <ActivityItem
              key={(item.id as string) || idx}
              item={item}
              groupType={group.type}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// TeamActivitySection — main exported component
// ---------------------------------------------------------------------------

export function TeamActivitySection({ activity, isLoading }: TeamActivitySectionProps) {
  const isLoadingState = isLoading || activity === undefined

  // Loading state
  if (isLoadingState) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Team Activity</h2>
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      </BrandedCard>
    )
  }

  // Empty state
  if (activity.length === 0) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Team Activity</h2>
        <p
          style={{
            fontSize: typography.caption.size,
            lineHeight: typography.caption.lineHeight,
            color: colors.secondaryText,
            margin: 0,
          }}
        >
          Your team is standing by. Try asking something in the chat.
        </p>
      </BrandedCard>
    )
  }

  // Loaded state — grouped activity cards
  return (
    <BrandedCard hoverable={false}>
      <h2 style={sectionTitleStyle}>Team Activity</h2>
      <div>
        {activity.map((group, idx) => (
          <ActivityGroupCard
            key={group.type}
            group={group}
            isLast={idx === activity.length - 1}
          />
        ))}
      </div>
    </BrandedCard>
  )
}
