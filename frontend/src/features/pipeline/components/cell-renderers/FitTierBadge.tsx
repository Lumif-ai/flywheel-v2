import type { ICellRendererParams } from 'ag-grid-community'
import { badges, typography } from '@/lib/design-tokens'
import type { PipelineItem } from '../../types/pipeline'

type FitTierKey = keyof typeof badges.fitTier

export function FitTierBadge(props: ICellRendererParams<PipelineItem>) {
  const { data } = props
  if (!data) return null

  const tier = data.fit_tier
  if (!tier) {
    return (
      <span style={{ color: 'var(--secondary-text)', fontSize: typography.caption.size }}>
        &mdash;
      </span>
    )
  }

  const tierKey = tier.toLowerCase() as FitTierKey
  const palette = badges.fitTier[tierKey] ?? badges.fitTier.fair

  return (
    <div className="flex items-center h-full">
      <span
        className="badge-translucent"
        style={{
          background: palette.bg,
          color: palette.text,
        }}
      >
        {tier}
      </span>
    </div>
  )
}
