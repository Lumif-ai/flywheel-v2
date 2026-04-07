import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineListItem } from '../../types/pipeline'

const TIER_COLORS: Record<string, { bg: string; text: string }> = {
  strong: { bg: '#D1FAE5', text: '#059669' },
  medium: { bg: '#FEF3C7', text: '#D97706' },
  weak: { bg: '#FEE2E2', text: '#DC2626' },
}

export function FitTierBadge(props: ICellRendererParams<PipelineListItem>) {
  const { value } = props

  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const tier = String(value)
  const key = tier.toLowerCase()
  const colors = TIER_COLORS[key] ?? { bg: '#F3F4F6', text: '#6B7280' }

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          display: 'inline-block',
          padding: '2px 8px',
          borderRadius: '9999px',
          fontSize: '11px',
          fontWeight: 600,
          background: colors.bg,
          color: colors.text,
        }}
      >
        {tier}
      </span>
    </div>
  )
}
