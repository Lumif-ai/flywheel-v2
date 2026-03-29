import { useNavigate } from 'react-router'
import { Users, TrendingUp, Briefcase, DollarSign } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useRelationships } from '../hooks/useRelationships'
import { RelationshipCard } from './RelationshipCard'
import { EmptyState } from '@/components/ui/empty-state'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { registers, spacing, typography } from '@/lib/design-tokens'
import type { RelationshipType, RelationshipListItem } from '../types/relationships'

const TYPE_CONFIG: Record<
  RelationshipType,
  {
    label: string
    icon: LucideIcon
    emptyDescription: string
  }
> = {
  prospect: {
    label: 'Prospects',
    icon: Users,
    emptyDescription: 'Graduate accounts from your Pipeline to see them here.',
  },
  customer: {
    label: 'Customers',
    icon: TrendingUp,
    emptyDescription: 'Closed deals will appear here once accounts are marked as customers.',
  },
  advisor: {
    label: 'Advisors',
    icon: Briefcase,
    emptyDescription: 'Add advisor relationships from the Pipeline to track them here.',
  },
  investor: {
    label: 'Investors',
    icon: DollarSign,
    emptyDescription: 'Investor relationships graduated from the Pipeline will appear here.',
  },
}

function sortByUrgency(items: RelationshipListItem[]): RelationshipListItem[] {
  return [...items].sort((a, b) => {
    // Primary: signal_count descending (nulls last)
    if (b.signal_count !== a.signal_count) return b.signal_count - a.signal_count
    // Secondary: last_interaction_at descending (most recent first, nulls last)
    if (a.last_interaction_at === null && b.last_interaction_at === null) return 0
    if (a.last_interaction_at === null) return 1
    if (b.last_interaction_at === null) return -1
    return new Date(b.last_interaction_at).getTime() - new Date(a.last_interaction_at).getTime()
  })
}

export function RelationshipListPage({ type }: { type: RelationshipType }) {
  const navigate = useNavigate()
  const { data: items = [], isLoading, error, refetch } = useRelationships(type)
  const config = TYPE_CONFIG[type]
  const sortedItems = sortByUrgency(items)

  return (
    <div style={{ background: registers.relationship.background }} className="min-h-dvh">
      <div
        className="mx-auto w-full"
        style={{
          maxWidth: spacing.maxGrid,
          padding: `${spacing.section} ${spacing.pageDesktop}`,
        }}
      >
        {/* Page title */}
        <h1
          style={{
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
            lineHeight: typography.pageTitle.lineHeight,
            letterSpacing: typography.pageTitle.letterSpacing,
            color: 'var(--heading-text)',
            marginBottom: '8px',
          }}
        >
          {config.label}
        </h1>
        <p style={{ fontSize: '14px', color: 'var(--secondary-text)', marginBottom: spacing.section }}>
          {isLoading ? '' : `${sortedItems.length} relationship${sortedItems.length !== 1 ? 's' : ''}`}
        </p>

        {/* Error state */}
        {error && !isLoading && (
          <div
            className="rounded-xl p-6 text-center"
            style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <p style={{ color: '#dc2626', fontSize: '14px', marginBottom: '12px' }}>
              Failed to load {config.label.toLowerCase()}. Please try again.
            </p>
            <button
              onClick={() => refetch()}
              style={{
                fontSize: '13px',
                fontWeight: 500,
                color: '#E94D35',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading state: 6 shimmer skeletons */}
        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <ShimmerSkeleton key={i} className="h-40 rounded-xl" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && sortedItems.length === 0 && (
          <EmptyState
            icon={config.icon}
            title={`No ${config.label.toLowerCase()} yet`}
            description={config.emptyDescription}
            actionLabel="Go to Pipeline"
            onAction={() => navigate('/pipeline')}
          />
        )}

        {/* Card grid */}
        {!isLoading && sortedItems.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sortedItems.map((item) => (
              <RelationshipCard key={item.id} item={item} type={type} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
