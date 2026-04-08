import { BrandedCard } from '@/components/ui/branded-card'
import { Skeleton } from '@/components/ui/skeleton'
import { typography, colors, spacing } from '@/lib/design-tokens'

interface DailyBriefSectionProps {
  narrative: string | undefined
  isLoading: boolean
}

/**
 * DailyBriefSection displays the LLM-generated narrative summary at the top
 * of the left column. Shows skeleton lines while loading, the narrative text
 * when loaded, or an empty-state message when there is no content.
 *
 * No manual refresh — React Query refetches on mount automatically (BRIEF-02).
 */
export function DailyBriefSection({ narrative, isLoading }: DailyBriefSectionProps) {
  const isLoadingState = isLoading || narrative === undefined

  // Empty state: not loading but narrative is an empty string
  if (!isLoadingState && narrative === '') {
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
          Daily Brief
        </h2>
        <p
          style={{
            fontSize: typography.caption.size,
            lineHeight: typography.caption.lineHeight,
            color: colors.secondaryText,
            margin: 0,
          }}
        >
          Your daily brief will appear here once you have some activity.
        </p>
      </BrandedCard>
    )
  }

  // Loading state: skeleton lines
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
          Daily Brief
        </h2>
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-[85%]" />
          <Skeleton className="h-4 w-[60%]" />
        </div>
      </BrandedCard>
    )
  }

  // Loaded state: narrative with warm styling
  return (
    <BrandedCard
      hoverable={false}
      className="!bg-[var(--brand-tint-warm)]"
    >
      <div
        style={{
          borderLeft: `3px solid ${colors.brandCoral}`,
          paddingLeft: spacing.element,
        }}
      >
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
          Daily Brief
        </h2>
        <p
          style={{
            fontSize: typography.body.size,
            fontWeight: typography.body.weight,
            lineHeight: '1.8',
            color: colors.bodyText,
            margin: 0,
          }}
        >
          {narrative}
        </p>
      </div>
    </BrandedCard>
  )
}
