import type { ComparisonQuoteCell } from '../../types/broker'
import { formatCurrency, isInsufficientLimit } from './comparison-utils'
import { cn } from '@/lib/cn'

interface ComparisonCellProps {
  cell: ComparisonQuoteCell | undefined
  requiredLimit: number | null
  currency: string
  highlightBest: boolean
}

export function ComparisonCell({
  cell,
  requiredLimit,
  currency,
  highlightBest,
}: ComparisonCellProps) {
  const baseCls = 'px-3 py-2 border-b border-r whitespace-nowrap'

  // No quote for this carrier/coverage
  if (!cell) {
    return (
      <td className={cn(baseCls, 'bg-gray-50 text-center')}>
        <span className="text-xs text-gray-400">No quote</span>
      </td>
    )
  }

  // Critical exclusion
  if (cell.has_critical_exclusion) {
    return (
      <td className={cn(baseCls, 'bg-red-50 border-l-4 border-red-500')}>
        <div className="text-red-700 font-semibold text-sm">EXCLUDED</div>
        {cell.critical_exclusion_detail && (
          <div
            className="text-xs text-red-600 truncate max-w-[140px]"
            title={cell.critical_exclusion_detail}
          >
            {cell.critical_exclusion_detail}
          </div>
        )}
      </td>
    )
  }

  // Insufficient limit
  const insufficient = isInsufficientLimit(cell.limit_amount, requiredLimit)

  // TODO(phase-138): Compute best-price from comparison data
  // Best price highlight
  const isBest = highlightBest && (cell as ComparisonQuoteCell & { is_best_price?: boolean }).is_best_price

  return (
    <td
      className={cn(
        baseCls,
        insufficient && 'bg-amber-50 border-l-4 border-amber-400',
        isBest && !insufficient && 'text-green-700 bg-green-50'
      )}
    >
      <div className="text-sm font-semibold">
        {formatCurrency(cell.premium, currency)}
      </div>
      <div className="text-xs text-muted-foreground">
        {formatCurrency(cell.limit_amount, currency)} / {formatCurrency(cell.deductible, currency)} ded.
      </div>
    </td>
  )
}
