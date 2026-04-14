import { useMemo } from 'react'
import type { ComparisonCoverage } from '../../types/broker'
import {
  getUniqueCarriers,
  computeCarrierTotals,
  hasMeaningfulDifference,
  formatCurrency,
} from './comparison-utils'
import { ComparisonCell } from './ComparisonCell'
import { CarrierColumnHeader } from './CarrierColumnHeader'
import { TotalPremiumRow } from './TotalPremiumRow'

interface ComparisonGridProps {
  coverages: ComparisonCoverage[]
  currency: string
  selectedCarriers: Set<string>
  onToggleCarrier: (name: string) => void
  showDifferencesOnly: boolean
  highlightBest: boolean
}

export function ComparisonGrid({
  coverages,
  currency,
  selectedCarriers,
  onToggleCarrier,
  showDifferencesOnly,
  highlightBest,
}: ComparisonGridProps) {
  const carriers = useMemo(() => getUniqueCarriers(coverages), [coverages])

  const filteredCoverages = useMemo(() => {
    if (!showDifferencesOnly) return coverages
    const filtered = coverages.filter((c) => hasMeaningfulDifference(c))
    // Pitfall: if filtering removes ALL rows, show all instead
    return filtered.length > 0 ? filtered : coverages
  }, [coverages, showDifferencesOnly])

  // Totals are always computed over the FULL coverages list
  const totals = useMemo(
    () => computeCarrierTotals(coverages, carriers),
    [coverages, carriers]
  )

  if (coverages.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
        No coverage data available
      </div>
    )
  }

  return (
    <div className="overflow-auto max-h-[calc(100vh-280px)] relative border rounded-lg">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th
              className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-50 border-b border-r min-w-[200px]"
              style={{ position: 'sticky', top: 0, left: 0, zIndex: 30 }}
            >
              Coverage
            </th>
            {carriers.map((carrier) => (
              <CarrierColumnHeader
                key={carrier.name}
                carrier={carrier}
                checked={selectedCarriers.has(carrier.name)}
                onToggle={onToggleCarrier}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {filteredCoverages.map((coverage) => (
            <tr key={coverage.coverage_id}>
              <td
                className="px-4 py-2 border-b border-r font-medium text-sm min-w-[200px] bg-white"
                style={{ position: 'sticky', left: 0, zIndex: 10 }}
              >
                <div>{coverage.coverage_type}</div>
                {coverage.required_limit != null && (
                  <div className="text-xs text-muted-foreground">
                    Required: {formatCurrency(coverage.required_limit, currency)}
                  </div>
                )}
              </td>
              {carriers.map((carrier) => {
                const cell = coverage.quotes.find(
                  (q) => q.carrier_name === carrier.name
                )
                return (
                  <ComparisonCell
                    key={carrier.name}
                    cell={cell}
                    requiredLimit={coverage.required_limit}
                    currency={currency}
                    highlightBest={highlightBest}
                  />
                )
              })}
            </tr>
          ))}
        </tbody>
        <TotalPremiumRow
          carriers={carriers}
          totals={totals}
          currency={currency}
          selectedCarriers={selectedCarriers}
        />
      </table>
    </div>
  )
}
