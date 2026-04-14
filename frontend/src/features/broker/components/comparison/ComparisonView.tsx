import { useState, useMemo, useCallback } from 'react'
import { BarChart3 } from 'lucide-react'
import { toast } from 'sonner'
import type { ComparisonMatrix } from '../../types/broker'
import { exportComparison } from '../../api'
import { getUniqueCarriers } from './comparison-utils'
import { CriticalExclusionAlert } from './CriticalExclusionAlert'
import { ComparisonToolbar } from './ComparisonToolbar'
import { ComparisonTabs } from './ComparisonTabs'

interface ComparisonViewProps {
  data: ComparisonMatrix
  currency: string
  projectId: string
}

export function ComparisonView({ data, currency, projectId }: ComparisonViewProps) {
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

  const [isExporting, setIsExporting] = useState(false)

  const handleExport = useCallback(async () => {
    setIsExporting(true)
    try {
      const quoteIds = data.coverages
        .flatMap((c) => c.quotes)
        .filter((q) => selectedCarriers.has(q.carrier_name))
        .map((q) => q.quote_id)
      await exportComparison(projectId, quoteIds.length > 0 ? quoteIds : undefined)
      toast.success('Comparison exported successfully')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setIsExporting(false)
    }
  }, [data.coverages, selectedCarriers, projectId])

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
        onExport={handleExport}
        isExporting={isExporting}
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
