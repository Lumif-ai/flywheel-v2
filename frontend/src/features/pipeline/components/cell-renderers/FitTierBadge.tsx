import type { ICellRendererParams } from 'ag-grid-community'
import { StatusBadge, type StatusBadgeColors } from '@/shared/grid/cell-renderers'

const FIT_TIER_COLORS: StatusBadgeColors = {
  strong: { bg: '#D1FAE5', text: '#059669' },
  medium: { bg: '#FEF3C7', text: '#D97706' },
  weak: { bg: '#FEE2E2', text: '#DC2626' },
}

export function FitTierBadge(props: ICellRendererParams) {
  return <StatusBadge {...props} colorMap={FIT_TIER_COLORS} />
}
