import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertTriangle } from 'lucide-react'
import { useComparison } from '../hooks/useBrokerQuotes'
import type { ComparisonQuoteCell, ComparisonCoverage } from '../types/broker'

interface ComparisonMatrixProps {
  projectId: string
  currency?: string
}

function formatCurrency(value: number | null, currency: string): string {
  if (value === null) return '\u2014'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(value)
}

function getCellStyles(cell: ComparisonQuoteCell, requiredLimit: number | null): string {
  if (cell.has_critical_exclusion) {
    return 'bg-red-50 border-l-4 border-red-500'
  }
  if (cell.is_recommended) {
    return 'bg-green-50 border-l-4 border-green-500'
  }
  if (cell.is_best_price) {
    return 'bg-green-50'
  }
  if (cell.is_best_coverage) {
    return 'bg-blue-50'
  }
  if (requiredLimit && cell.limit_amount && cell.limit_amount < requiredLimit) {
    return 'bg-yellow-50 border-l-4 border-yellow-500'
  }
  return 'bg-white'
}

function QuoteCell({ cell, requiredLimit, currency }: { cell: ComparisonQuoteCell; requiredLimit: number | null; currency: string }) {
  const styles = getCellStyles(cell, requiredLimit)
  const insufficientLimit = requiredLimit && cell.limit_amount && cell.limit_amount < requiredLimit

  return (
    <td className={`px-3 py-2 text-sm ${styles}`}>
      <div className="space-y-1">
        <div className="font-medium">{formatCurrency(cell.premium, currency)}</div>
        {cell.deductible != null && (
          <div className="text-xs text-muted-foreground">Ded: {formatCurrency(cell.deductible, currency)}</div>
        )}
        {cell.limit_amount != null && (
          <div className="text-xs text-muted-foreground">Limit: {formatCurrency(cell.limit_amount, currency)}</div>
        )}

        {/* Badges */}
        {cell.has_critical_exclusion && (
          <div className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3 text-red-600" />
            <span className="text-xs text-red-700" title={cell.critical_exclusion_detail || undefined}>
              Critical exclusion
            </span>
          </div>
        )}
        {cell.is_recommended && (
          <Badge className="text-xs bg-green-100 text-green-700">Recommended</Badge>
        )}
        {cell.is_best_price && !cell.is_recommended && (
          <Badge className="text-xs bg-green-100 text-green-700">Best Price</Badge>
        )}
        {cell.is_best_coverage && !cell.is_recommended && (
          <Badge className="text-xs bg-blue-100 text-blue-700">Best Coverage</Badge>
        )}
        {insufficientLimit && (
          <span className="text-xs text-yellow-700">Insufficient limit</span>
        )}
      </div>
    </td>
  )
}

function EmptyCell() {
  return (
    <td className="px-3 py-2 text-sm text-center bg-gray-50">
      <span className="text-gray-400">&mdash;</span>
      <div className="text-xs text-muted-foreground">No quote</div>
    </td>
  )
}

function CoverageRow({ coverage, carriers, currency }: { coverage: ComparisonCoverage; carriers: string[]; currency: string }) {
  return (
    <tr className="border-b">
      <td className="px-3 py-2 text-sm font-medium whitespace-nowrap">
        <div>{coverage.coverage_type}</div>
        <div className="text-xs text-muted-foreground">{coverage.category}</div>
        {coverage.required_limit != null && (
          <div className="text-xs text-muted-foreground">
            Required: {formatCurrency(coverage.required_limit, currency)}
          </div>
        )}
      </td>
      {carriers.map((carrierName) => {
        const cell = coverage.quotes.find((q) => q.carrier_name === carrierName)
        if (!cell) return <EmptyCell key={carrierName} />
        return <QuoteCell key={carrierName} cell={cell} requiredLimit={coverage.required_limit} currency={currency} />
      })}
    </tr>
  )
}

export function ComparisonMatrix({ projectId, currency = 'MXN' }: ComparisonMatrixProps) {
  const { data: matrix, isLoading } = useComparison(projectId, true)

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    )
  }

  if (!matrix || matrix.coverages.length === 0) return null

  // Derive unique carrier names from the data
  const carriers = Array.from(
    new Set(
      matrix.coverages.flatMap((c) => c.quotes.map((q) => q.carrier_name))
    )
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">Quote Comparison</h3>
          <p className="text-sm text-muted-foreground">
            {matrix.total_carriers} carriers across {matrix.total_coverages} coverages
          </p>
        </div>
      </div>

      {matrix.partial && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-50 border border-yellow-200">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <span className="text-sm text-yellow-800">
            Partial comparison — fewer than 2 carriers have submitted quotes
          </span>
        </div>
      )}

      {matrix.currency_mismatch && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-50 border border-yellow-200">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <span className="text-sm text-yellow-800">
            Currency mismatch detected — review quote currencies
          </span>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="px-3 py-2 text-xs font-medium text-muted-foreground uppercase">Coverage</th>
              {carriers.map((name) => (
                <th key={name} className="px-3 py-2 text-xs font-medium text-muted-foreground uppercase">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.coverages.map((coverage) => (
              <CoverageRow
                key={coverage.coverage_id}
                coverage={coverage}
                carriers={carriers}
                currency={currency}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
