import { useState, useMemo, useCallback } from 'react'
import { BarChart3 } from 'lucide-react'
import type { ComparisonMatrix } from '../../types/broker'
import { getUniqueCarriers } from './comparison-utils'
import { CriticalExclusionAlert } from './CriticalExclusionAlert'
import { ComparisonToolbar } from './ComparisonToolbar'
import { ComparisonTabs } from './ComparisonTabs'

interface ComparisonViewProps {
  data: ComparisonMatrix
  currency: string
}

export function ComparisonView({ data, currency }: ComparisonViewProps) {
  const allCarriers = useMemo(
    () => getUniqueCarriers(data.coverages),
    [data.coverages]
  )

  const [selectedCarriers, setSelectedCarriers] = useState<Set<string>>(
    () => new Set(allCarriers.map((c) => c.name))
  )
  const [showDifferencesOnly, setShowDifferencesOnly] = useState(true)
  const [highlightBest, setHighlightBest] = useState(false)

  const onToggleCarrier = useCallback(
    (name: string) => {
      setSelectedCarriers((prev) => {
        const next = new Set(prev)
        if (next.has(name)) {
          // At least 1 carrier must remain selected
          if (next.size <= 1) return prev
          next.delete(name)
        } else {
          next.add(name)
        }
        return next
      })
    },
    []
  )

  const filteredCoverages = useMemo(
    () =>
      data.coverages.map((cov) => ({
        ...cov,
        quotes: cov.quotes.filter((q) => selectedCarriers.has(q.carrier_name)),
      })),
    [data.coverages, selectedCarriers]
  )

  if (data.coverages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <BarChart3 className="h-10 w-10 text-muted-foreground mb-3" />
        <h3 className="text-lg font-medium">No quotes to compare yet</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Add carriers and upload quotes to see the comparison matrix.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <CriticalExclusionAlert coverages={data.coverages} />
      <ComparisonToolbar
        showDifferencesOnly={showDifferencesOnly}
        onToggleDifferences={() => setShowDifferencesOnly((v) => !v)}
        highlightBest={highlightBest}
        onToggleHighlight={() => setHighlightBest((v) => !v)}
      />
      <ComparisonTabs
        coverages={filteredCoverages}
        currency={currency}
        selectedCarriers={selectedCarriers}
        onToggleCarrier={onToggleCarrier}
        showDifferencesOnly={showDifferencesOnly}
        highlightBest={highlightBest}
      />
    </div>
  )
}
