import React from 'react'
import { BrandedCard } from '@/components/ui/branded-card'
import { Skeleton } from '@/components/ui/skeleton'
import { typography, colors, spacing } from '@/lib/design-tokens'
import type { MarketPatternsData, PainPattern } from '@/features/briefing/types/briefing-v2'

interface MarketPatternsSectionProps {
  patterns: MarketPatternsData | undefined
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
// Confidence badge colors — matches fitTier badge palette in design-tokens
// ---------------------------------------------------------------------------

const CONFIDENCE_COLORS: Record<string, { bg: string; text: string }> = {
  high:   { bg: 'rgba(34, 197, 94, 0.1)',    text: '#16a34a' },
  medium: { bg: 'rgba(245, 158, 11, 0.1)',   text: '#d97706' },
  low:    { bg: 'rgba(107, 114, 128, 0.08)', text: '#6b7280' },
}

// ---------------------------------------------------------------------------
// isHairOnFire — detect "HAIR ON FIRE" signal in raw content string
// ---------------------------------------------------------------------------

const isHairOnFire = (content: string): boolean =>
  content.toUpperCase().includes('HAIR ON FIRE')

// ---------------------------------------------------------------------------
// PainPatternRow — single pattern row with label + confidence + HOF badge
// ---------------------------------------------------------------------------

function PainPatternRow({ pattern, isLast }: { pattern: PainPattern; isLast: boolean }) {
  const conf = CONFIDENCE_COLORS[pattern.confidence] ?? CONFIDENCE_COLORS.low

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.tight,
        paddingTop: spacing.tight,
        paddingBottom: spacing.tight,
        borderBottom: isLast ? 'none' : `1px solid ${colors.subtleBorder}`,
      }}
    >
      <span style={{ flex: 1, fontWeight: 500, color: colors.headingText }}>{pattern.label}</span>
      <span
        style={{
          padding: '2px 8px',
          borderRadius: 99,
          fontSize: '0.75rem',
          fontWeight: 600,
          backgroundColor: conf.bg,
          color: conf.text,
        }}
      >
        {pattern.confidence}
      </span>
      {isHairOnFire(pattern.content) && (
        <span
          style={{
            padding: '2px 8px',
            borderRadius: 99,
            fontSize: '0.75rem',
            fontWeight: 600,
            backgroundColor: 'rgba(233, 77, 53, 0.12)',
            color: colors.brandCoral,
          }}
        >
          Hair on fire
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// MarketPatternsSection — main exported component
// ---------------------------------------------------------------------------

export function MarketPatternsSection({ patterns, isLoading }: MarketPatternsSectionProps) {
  // Loading state
  if (isLoading) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Market Pain Patterns</h2>
        <div className="space-y-3">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-4/5" />
          <Skeleton className="h-8 w-3/5" />
        </div>
      </BrandedCard>
    )
  }

  // Empty state — no patterns yet
  if (!patterns || patterns.patterns.length === 0) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Market Pain Patterns</h2>
        <p
          style={{
            fontSize: typography.caption.size,
            lineHeight: typography.caption.lineHeight,
            color: colors.secondaryText,
            margin: 0,
          }}
        >
          No patterns yet — run /synthesize after meetings to surface market intelligence.
        </p>
      </BrandedCard>
    )
  }

  // Loaded state — show top 5 patterns
  const topPatterns = patterns.patterns.slice(0, 5)

  return (
    <BrandedCard hoverable={false}>
      <h2 style={sectionTitleStyle}>Market Pain Patterns</h2>
      <div>
        {topPatterns.map((pattern, idx) => (
          <PainPatternRow
            key={pattern.slug}
            pattern={pattern}
            isLast={idx === topPatterns.length - 1}
          />
        ))}
      </div>
    </BrandedCard>
  )
}
