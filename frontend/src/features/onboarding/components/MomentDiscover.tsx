/**
 * MomentDiscover - Second onboarding moment.
 *
 * Shows intelligence cascading in as the company-intel crawl runs.
 * Categories animate in with stagger. Shimmer skeletons for pending.
 * Auto-advances to align after crawl completes + 1s pause.
 */

import { useEffect, useRef } from 'react'
import {
  Building2,
  Package,
  Users,
  TrendingUp,
  Cpu,
  UserCheck,
  DollarSign,
  type LucideIcon,
} from 'lucide-react'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { animationClasses, staggerDelay } from '@/lib/animations'
import type { CrawlItem } from '../hooks/useOnboarding'

// ---------------------------------------------------------------------------
// Category icon mapping
// ---------------------------------------------------------------------------

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  company_info: Building2,
  product: Package,
  team: Users,
  market: TrendingUp,
  technology: Cpu,
  customer: UserCheck,
  financial: DollarSign,
}

const CATEGORY_LABELS = ['Company', 'Products', 'Customers', 'Market', 'Technology', 'Team', 'Financial']

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MomentDiscoverProps {
  crawlItems: CrawlItem[]
  crawlTotal: number
  crawlStatus: string | null
  isComplete: boolean
  onComplete: () => void
}

// ---------------------------------------------------------------------------
// Shimmer skeleton for loading categories
// ---------------------------------------------------------------------------

function ShimmerSkeleton() {
  return (
    <div className="rounded-md border border-border/30 p-3 space-y-2">
      <div className={`h-4 w-32 rounded bg-muted/50 ${animationClasses.shimmer}`} />
      <div className="flex gap-1.5">
        <div className={`h-6 w-20 rounded-full bg-muted/30 ${animationClasses.shimmer}`} />
        <div className={`h-6 w-16 rounded-full bg-muted/30 ${animationClasses.shimmer}`} />
        <div className={`h-6 w-24 rounded-full bg-muted/30 ${animationClasses.shimmer}`} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MomentDiscover({
  crawlItems,
  crawlTotal,
  crawlStatus,
  isComplete,
  onComplete,
}: MomentDiscoverProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const autoAdvanceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-scroll as new items arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [crawlItems.length])

  // Auto-advance 1 second after crawl completes
  useEffect(() => {
    if (isComplete) {
      autoAdvanceRef.current = setTimeout(() => {
        onComplete()
      }, 3000)
    }
    return () => {
      if (autoAdvanceRef.current) {
        clearTimeout(autoAdvanceRef.current)
      }
    }
  }, [isComplete, onComplete])

  // How many shimmer slots to show while loading
  const shimmerCount = isComplete ? 0 : Math.max(0, 3 - crawlItems.length)

  return (
    <div
      className={animationClasses.fadeSlideUp}
      style={{
        maxWidth: spacing.maxReading,
        width: '100%',
        margin: '0 auto',
      }}
    >
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: spacing.section }}>
        <h1
          style={{
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
            lineHeight: typography.pageTitle.lineHeight,
            color: colors.headingText,
            marginBottom: spacing.tight,
          }}
        >
          {isComplete ? 'Discovery complete' : (
            <>
              Discovering intelligence
              <span className="inline-flex ml-1">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
              </span>
            </>
          )}
        </h1>

        {crawlTotal > 0 ? (
          <p
            className="tabular-nums"
            style={{
              fontSize: '24px',
              fontWeight: '600',
              color: colors.brandCoral,
            }}
          >
            {crawlTotal} items found
          </p>
        ) : crawlStatus ? (
          <p
            className="animate-pulse"
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            {crawlStatus}
          </p>
        ) : null}
      </div>

      {/* Category cards */}
      <div
        className="space-y-3 overflow-y-auto rounded-lg"
        style={{
          maxHeight: '28rem',
          padding: spacing.card,
          border: `1px solid ${colors.subtleBorder}`,
        }}
      >
        {crawlItems.map((group, i) => {
          const IconComponent = CATEGORY_ICONS[group.category] ?? Building2
          return (
            <div
              key={i}
              className={animationClasses.fadeSlideUp}
              style={{
                animationDelay: staggerDelay(i),
                animationFillMode: 'both',
                borderRadius: '8px',
                border: `1px solid ${colors.subtleBorder}`,
                background: colors.brandTint,
                padding: '12px 16px',
              }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <IconComponent className="h-4 w-4 shrink-0" style={{ color: colors.brandCoral }} />
                <span
                  style={{
                    fontSize: typography.body.size,
                    fontWeight: '500',
                    color: colors.headingText,
                  }}
                >
                  {group.label}
                </span>
                <span
                  className="ml-auto"
                  style={{
                    fontSize: typography.caption.size,
                    color: colors.secondaryText,
                  }}
                >
                  {group.items.length}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {group.items.map((item, j) => (
                  <span
                    key={j}
                    className="inline-block rounded-full px-2.5 py-0.5"
                    style={{
                      fontSize: typography.caption.size,
                      background: colors.cardBg,
                      border: `1px solid ${colors.subtleBorder}`,
                      color: colors.bodyText,
                    }}
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )
        })}

        {/* Shimmer skeletons for not-yet-loaded categories */}
        {Array.from({ length: shimmerCount }).map((_, i) => (
          <ShimmerSkeleton key={`shimmer-${i}`} />
        ))}

        {/* Status spinner when no items yet */}
        {crawlItems.length === 0 && crawlStatus && (
          <div className="flex items-center justify-center gap-2 py-8" style={{ color: colors.secondaryText }}>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            <span style={{ fontSize: typography.caption.size }}>{crawlStatus}</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
